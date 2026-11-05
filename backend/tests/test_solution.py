import json

import pytest
from fastapi.testclient import TestClient

import main
from ai import review
from ai.review import CRITERIA, build_review_input, validate_review
from engine.session import Session
from scenarios import MISSIONS

WEB_IP, WAS_IP = "192.168.111.100", "192.168.111.200"


@pytest.fixture
def api(monkeypatch):
    # AI는 부르지 않고, 힌트는 가짜 문장으로 대신합니다.
    monkeypatch.setattr(main, "generate_hint", lambda ctx: f"{ctx.level}단계 힌트 문장이에요, 천천히 보세요.")
    return TestClient(main.app)


def new_session(api, mission="mission01"):
    return api.post("/api/sessions", json={"mission_id": mission}).json()["sid"]


def use_hints(api, sid, n):
    for _ in range(n):
        assert api.post(f"/api/sessions/{sid}/hint").status_code == 200


def ask(api, sid):
    return api.post(f"/api/sessions/{sid}/solution")


# ---------------------------------------------------------------- 잠금: 힌트 3개를 다 써야 열림
@pytest.mark.parametrize("used", [0, 1, 2])
def test_locked_until_all_hints_used(api, used):
    sid = new_session(api)
    use_hints(api, sid, used)
    r = ask(api, sid)
    assert r.status_code == 409 and f"지금 {used}개 사용" in r.json()["detail"]
    assert api.get(f"/api/sessions/{sid}").json()["solution"] is None


@pytest.mark.parametrize("mission", ["mission01", "mission02", "mission03"])
def test_solution_text_never_leaks_before_it_is_requested(api, mission):
    sid = new_session(api, mission)
    use_hints(api, sid, 2)
    ask(api, sid)  # 거절됨
    text = api.get(f"/api/sessions/{sid}").text
    cause = MISSIONS[mission].solution["cause"]
    assert cause not in text and '"solution":null' in text.replace(" ", "")


def test_unlocked_after_three_hints(api):
    sid = new_session(api)
    use_hints(api, sid, 3)
    d = ask(api, sid).json()
    sol = d["solution"]
    assert set(sol) == {"cause", "path", "fix", "lesson", "my_checks"}
    assert "Tomcat" in sol["cause"] and any("systemctl start tomcat10" in f for f in sol["fix"])
    assert sol["my_checks"] == {"evidence": [], "root_cause_checked": False, "hypothesis_submitted": False}


def test_my_checks_reflect_what_the_learner_actually_did(api):
    sid = new_session(api)
    api.post(f"/api/sessions/{sid}/command", json={"server": "WEB", "command": f"curl http://{WEB_IP}"})
    api.post(f"/api/sessions/{sid}/command", json={"server": "WAS", "command": "systemctl status tomcat10"})
    use_hints(api, sid, 3)
    checks = ask(api, sid).json()["solution"]["my_checks"]
    assert checks["root_cause_checked"] is True and len(checks["evidence"]) == 2


def test_solution_view_is_recorded_once(api):
    sid = new_session(api)
    use_hints(api, sid, 3)
    ask(api, sid)
    api.post(f"/api/sessions/{sid}/command", json={"server": "WEB", "command": "hostname"})
    assert ask(api, sid).status_code == 200  # 다시 눌러도 오류 없이 같은 해설
    s = main.SESSIONS[sid]
    assert s.solution_viewed is True and s.solution_after_seq == 0  # 처음 본 시점(명령어 0개 뒤)이 유지됨


def test_solution_is_never_given_after_completion(api):
    sid = new_session(api)
    use_hints(api, sid, 3)
    for server, cmd in [("WAS", "systemctl start tomcat10"), ("WEB", f"curl http://{WAS_IP}:8080"),
                        ("WEB", f"curl http://{WEB_IP}")]:
        api.post(f"/api/sessions/{sid}/command", json={"server": server, "command": cmd})
    r = ask(api, sid)
    assert r.status_code == 409 and "이미 정상화" in r.json()["detail"]


def test_viewing_then_finishing_keeps_the_solution_and_the_flag(api):
    sid = new_session(api)
    use_hints(api, sid, 3)
    ask(api, sid)
    for server, cmd in [("WAS", "systemctl start tomcat10"), ("WEB", f"curl http://{WAS_IP}:8080"),
                        ("WEB", f"curl http://{WEB_IP}")]:
        d = api.post(f"/api/sessions/{sid}/command", json={"server": server, "command": cmd}).json()
    assert d["progress"]["completed"] is True and d["solution"] is not None
    assert build_review_input(main.SESSIONS[sid])["solution_viewed"] is True


def test_reset_hides_solution_again(api):
    sid = new_session(api)
    use_hints(api, sid, 3)
    ask(api, sid)
    d = api.post(f"/api/sessions/{sid}/reset").json()
    assert d["solution"] is None and d["hints"] == []
    assert ask(api, sid).status_code == 409  # 힌트도 초기화됐으니 다시 잠김


def test_unknown_session_is_404(api):
    assert ask(api, "nope").status_code == 404


# ---------------------------------------------------------------- 해설 내용이 실제로 맞는지
@pytest.mark.parametrize("mission", ["mission01", "mission02", "mission03"])
def test_every_mission_has_a_complete_learner_facing_solution(mission):
    sol = MISSIONS[mission].solution
    assert sol["cause"] and sol["lesson"] and len(sol["path"]) >= 3 and len(sol["fix"]) >= 2
    assert all(isinstance(x, str) and x for x in sol["path"] + sol["fix"])


def test_mission02_solution_fix_command_really_works():
    s = Session(MISSIONS["mission02"])
    assert "[ 2] 8080/tcp" in s.run("WAS", "ufw status numbered")["output"] and "REJECT" in s.run("WAS", "ufw status numbered")["output"]
    s.run("WAS", "ufw delete 2")  # 해설에 적힌 명령어 그대로
    s.run("WEB", f"curl http://{WAS_IP}:8080")
    s.run("WEB", f"curl http://{WEB_IP}")
    assert s.progress()["completed"] is True


def test_mission02_alternative_fix_in_solution_really_works():
    s = Session(MISSIONS["mission02"])
    s.run("WAS", f"ufw insert 1 allow from {WEB_IP} to any port 8080 proto tcp")
    s.run("WEB", f"curl http://{WAS_IP}:8080")
    s.run("WEB", f"curl http://{WEB_IP}")
    assert s.progress()["completed"] is True


# ---------------------------------------------------------------- AI 리뷰: 해설을 봤으면 '원인 분석 우수'는 불가
def raw_review(root_rating="우수"):
    return json.dumps({
        "overall": "종합 평가예요.",
        "scores": [{"key": k, "rating": root_rating if k == "root_cause_analysis" else "우수", "reason": f"{k} 이유"}
                   for k, _ in CRITERIA],
        "strengths": [], "improvements": [], "senior_advice": [], "next_learning": [],
    }, ensure_ascii=False)


def rating(out, key):
    return next(s for s in out["scores"] if s["key"] == key)


def test_review_input_flags_solution_view():
    s = Session(MISSIONS["mission01"])
    assert build_review_input(s)["solution_viewed"] is False
    s.run("WEB", "hostname")
    s.view_solution()
    pl = build_review_input(s)
    assert pl["solution_viewed"] is True and pl["solution_viewed_after_command_seq"] == 1


def test_root_cause_excellent_is_capped_when_solution_was_viewed():
    out = validate_review(raw_review("우수"), {1}, solution_viewed=True)
    rc = rating(out, "root_cause_analysis")
    assert rc["rating"] == "보통" and "해설" in rc["reason"]
    assert rating(out, "verification")["rating"] == "우수"  # 다른 항목은 건드리지 않음


def test_ratings_unchanged_when_solution_not_viewed_or_already_lower():
    assert rating(validate_review(raw_review("우수"), {1}), "root_cause_analysis")["rating"] == "우수"
    out = validate_review(raw_review("미흡"), {1}, solution_viewed=True)
    assert rating(out, "root_cause_analysis") == {**rating(out, "root_cause_analysis"), "rating": "미흡",
                                                  "reason": "root_cause_analysis 이유"}


def test_generate_review_applies_the_cap_from_the_payload(monkeypatch):
    monkeypatch.setattr(review, "_client", lambda: object())
    monkeypatch.setattr(review, "_request", lambda client, payload: raw_review("우수"))
    s = Session(MISSIONS["mission01"])
    s.run("WEB", "hostname")
    s.view_solution()
    out = review.generate_review(build_review_input(s))
    assert rating(out, "root_cause_analysis")["rating"] == "보통"
    fresh = review.generate_review(build_review_input(Session(MISSIONS["mission01"])))
    assert rating(fresh, "root_cause_analysis")["rating"] == "우수"
