import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import ai.review as review_mod
import main
from ai.review import CRITERIA, ReviewError, build_review_input, generate_review, validate_review
from engine.session import Session
from scenarios.mission01 import Mission01


def finished_session():
    s = Session(Mission01())
    s.run("WEB", "curl http://192.168.111.100")
    s.run("WAS", "systemctl status tomcat10")
    s.submit_hypothesis("WAS의 Tomcat이 꺼져 있어서 502가 난다")
    s.run("WAS", "systemctl start tomcat10")
    s.run("WEB", "curl http://192.168.111.200:8080")
    s.run("WEB", "curl http://192.168.111.100")
    assert s.progress()["completed"]
    return s


def sample_review(refs_strength=(2,), refs_improve=()):
    return {
        "overall": "잘 해결했어요.",
        "scores": [{"key": k, "rating": "우수", "reason": "기록상 좋았어요."} for k, _ in CRITERIA],
        "strengths": [{"text": "WAS 상태를 확인했어요.", "refs": list(refs_strength)}],
        "improvements": [{"text": "로그도 보면 좋아요.", "refs": list(refs_improve)}],
        "senior_advice": ["재발 방지를 위해 로그를 확인하세요."],
        "next_learning": [{"title": "방화벽 장애", "reason": "같은 502, 다른 원인"}],
    }


# ---------------------------------------------------------------- AI에 보내는 입력
def test_review_input_contains_log_verdict_and_root_cause():
    p = build_review_input(finished_session())
    assert [e["seq"] for e in p["action_log"]] == [1, 2, 3, 4, 5]
    assert p["real_root_cause"] == Mission01.root_cause
    v = p["simulator_verdict"]
    assert v["mission_completed"] and v["recovered"] and v["root_cause_directly_checked"]
    assert v["verified_after_recovery"] == {"was_direct": True, "web_via_nginx": True}
    assert p["hypotheses"] == [{"text": "WAS의 Tomcat이 꺼져 있어서 502가 난다", "submitted_after_command_seq": 2}]
    assert p["final_state"]["services_running"]["WAS:tomcat10"] is True
    assert 8080 in p["final_state"]["listening_ports"]["WAS"]


def test_review_input_has_no_invented_actions():
    s = Session(Mission01())
    s.run("WAS", "systemctl start tomcat10")
    s.run("WEB", "curl 192.168.111.200:8080")
    s.run("WEB", "curl 192.168.111.100")
    p = build_review_input(s)
    assert p["hypotheses"] == [] and p["simulator_verdict"]["root_cause_directly_checked"] is False
    assert [e["command"] for e in p["action_log"]] == [
        "systemctl start tomcat10", "curl 192.168.111.200:8080", "curl 192.168.111.100"]


# ---------------------------------------------------------------- 형식·근거 검사
def test_validate_adds_labels_orders_scores_and_drops_fake_refs():
    raw = sample_review(refs_strength=(2, 99), refs_improve=(1, 500))
    raw["scores"].reverse()
    out = validate_review(json.dumps(raw), valid_seqs={1, 2, 3})
    assert [s["key"] for s in out["scores"]] == [k for k, _ in CRITERIA]
    assert out["scores"][0]["label"] == "원인 분석 능력"
    assert out["strengths"][0]["refs"] == [2] and out["improvements"][0]["refs"] == [1]


@pytest.mark.parametrize("mutate", [
    lambda r: r["scores"].pop(),
    lambda r: r["scores"][0].update(rating="최고"),
    lambda r: r.pop("overall"),
    lambda r: r["scores"].append(dict(r["scores"][0])),
])
def test_validate_rejects_bad_structure(mutate):
    raw = sample_review()
    mutate(raw)
    with pytest.raises(Exception):
        validate_review(json.dumps(raw), {1, 2})


def test_validate_rejects_non_json():
    with pytest.raises(Exception):
        validate_review("이건 JSON이 아니에요", {1})


# ---------------------------------------------------------------- 모델 호출(가짜 클라이언트)
def fake_client(*responses):
    calls = []
    queue = list(responses)

    def create(**kw):
        calls.append(kw)
        return queue.pop(0)

    ns = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
                         messages=SimpleNamespace(create=create))
    return ns, calls


def resp(text="", stop="end_turn"):
    return SimpleNamespace(stop_reason=stop, content=[SimpleNamespace(type="text", text=text)] if text else [])


def test_generate_review_success_uses_schema_and_fallback(monkeypatch):
    client, calls = fake_client(resp(json.dumps(sample_review())))
    monkeypatch.setattr(review_mod, "_client", lambda: client)
    out = generate_review(build_review_input(finished_session()))
    assert out["overall"] == "잘 해결했어요."
    kw = calls[0]
    assert kw["model"] == "claude-opus-5-5"
    assert kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["fallbacks"] == "default" and "thinking" not in kw and "temperature" not in kw
    assert "기록에 없는 행동이나 생각을 추측하거나 지어내지 마세요" in kw["system"]
    sent = kw["messages"][0]["content"]
    assert "systemctl start tomcat10" in sent and "real_root_cause" in sent


def test_generate_review_retries_once_on_bad_json_then_succeeds(monkeypatch):
    client, calls = fake_client(resp("깨진 응답"), resp(json.dumps(sample_review())))
    monkeypatch.setattr(review_mod, "_client", lambda: client)
    assert generate_review(build_review_input(finished_session()))["overall"]
    assert len(calls) == 2


def test_generate_review_fails_honestly_after_two_bad_responses(monkeypatch):
    client, _ = fake_client(resp("깨짐1"), resp("깨짐2"))
    monkeypatch.setattr(review_mod, "_client", lambda: client)
    with pytest.raises(ReviewError) as e:
        generate_review(build_review_input(finished_session()))
    assert "형식" in e.value.message


@pytest.mark.parametrize("r,word", [(resp("", "refusal"), "답하지 못"), (resp("x", "max_tokens"), "끊겼"), (resp(""), "빈 답변")])
def test_request_errors_are_reported_not_faked(monkeypatch, r, word):
    client, _ = fake_client(r)
    monkeypatch.setattr(review_mod, "_client", lambda: client)
    with pytest.raises(ReviewError) as e:
        generate_review(build_review_input(finished_session()))
    assert word in e.value.message


def test_missing_api_key_gives_setup_guide(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ReviewError) as e:
        generate_review(build_review_input(finished_session()))
    assert e.value.status == 503 and ".env" in e.value.message


# ---------------------------------------------------------------- API
@pytest.fixture
def api():
    main.SESSIONS.clear()
    c = TestClient(main.app)
    sid = c.post("/api/sessions", json={"mission_id": "mission01"}).json()["sid"]
    return c, sid


def complete(c, sid):
    for server, cmd in [("WEB", "curl 192.168.111.100"), ("WAS", "systemctl status tomcat10"),
                        ("WAS", "systemctl start tomcat10"), ("WEB", "curl 192.168.111.200:8080"),
                        ("WEB", "curl 192.168.111.100")]:
        c.post(f"/api/sessions/{sid}/command", json={"server": server, "command": cmd})


def test_review_blocked_before_completion(api):
    c, sid = api
    r = c.post(f"/api/sessions/{sid}/review")
    assert r.status_code == 409 and "완료" in r.json()["detail"]
    c.post(f"/api/sessions/{sid}/command", json={"server": "WAS", "command": "systemctl start tomcat10"})
    assert c.post(f"/api/sessions/{sid}/review").status_code == 409  # 복구만 한 상태


def test_review_without_key_returns_guide_and_saves_nothing(api, monkeypatch):
    c, sid = api
    complete(c, sid)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = c.post(f"/api/sessions/{sid}/review")
    assert r.status_code == 503 and ".env" in r.json()["detail"]
    v = c.get(f"/api/sessions/{sid}").json()
    assert v["review"] is None and v["progress"]["steps"][-1]["done"] is False


def test_review_success_is_saved_cached_and_resettable(api, monkeypatch):
    c, sid = api
    complete(c, sid)
    calls = []
    monkeypatch.setattr(main, "generate_review", lambda payload: calls.append(payload) or validate_review(
        json.dumps(sample_review()), {e["seq"] for e in payload["action_log"]}))
    v = c.post(f"/api/sessions/{sid}/review").json()
    assert v["review"]["overall"] and v["progress"]["steps"][-1] == {"key": "review", "label": "AI 리뷰", "done": True}
    c.post(f"/api/sessions/{sid}/review")
    assert len(calls) == 1  # 이미 받은 리뷰는 다시 호출하지 않음
    c.post(f"/api/sessions/{sid}/review?force=true")
    assert len(calls) == 2
    assert c.get(f"/api/sessions/{sid}").json()["review"] is not None  # 새로고침해도 유지
    v = c.post(f"/api/sessions/{sid}/reset").json()
    assert v["review"] is None and v["progress"]["steps"][-1]["done"] is False


def test_review_failure_status_and_message_pass_through(api, monkeypatch):
    c, sid = api
    complete(c, sid)

    def boom(payload):
        raise ReviewError("지금 AI 요청이 몰려 있어요.", 429)

    monkeypatch.setattr(main, "generate_review", boom)
    r = c.post(f"/api/sessions/{sid}/review")
    assert r.status_code == 429 and "몰려" in r.json()["detail"]
    assert c.get(f"/api/sessions/{sid}").json()["review"] is None
    # 실패 뒤에도 다시 요청할 수 있어야 함 (진행 중 표시가 남지 않음)
    monkeypatch.setattr(main, "generate_review", lambda p: validate_review(json.dumps(sample_review()), {1}))
    assert c.post(f"/api/sessions/{sid}/review").status_code == 200


def test_unexpected_error_does_not_leak_details(api, monkeypatch):
    c, sid = api
    complete(c, sid)
    monkeypatch.setattr(main, "generate_review", lambda p: 1 / 0)
    r = c.post(f"/api/sessions/{sid}/review")
    assert r.status_code == 500 and "division" not in r.text


def test_public_view_never_contains_root_cause_or_internal_input(api):
    c, sid = api
    complete(c, sid)
    assert Mission01.root_cause not in c.get(f"/api/sessions/{sid}").text
