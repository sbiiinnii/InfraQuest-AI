import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import ai.hint as hint_mod
import main
from ai.hint import MAX_HINTS, build_hint_context, check_hint, generate_hint
from ai.llm import AIError
from ai.review import build_review_input
from engine.session import Session
from scenarios.mission01 import Mission01
from scenarios.mission02 import Mission02


def ctx_for(scn_cls, level, cmds=()):
    s = Session(scn_cls())
    for server, c in cmds:
        s.run(server, c)
    return build_hint_context(s, level), s


# ---------------------------------------------------------------- 서버 쪽 규칙 검사 (미션 1)
M1_OK = {
    1: "증상에서 출발해서, 요청이 지나가는 길을 순서대로 따라가며 어디에서 끊기는지 좁혀 보세요.",
    2: "요청을 받아서 처리하는 뒤쪽 서버 쪽의 서비스 상태를 살펴보면 좋겠어요.",
    3: "WAS 서버에서 `systemctl status tomcat10` 를 실행하고, 출력의 Active 줄을 살펴보세요.",
}


@pytest.mark.parametrize("level", [1, 2, 3])
def test_good_hints_pass_for_each_level(level):
    ctx, _ = ctx_for(Mission01, level)
    assert check_hint(M1_OK[level], ctx) is None


@pytest.mark.parametrize("level,text,word", [
    (1, "WAS 서버를 살펴보면 좋겠어요. 차근차근 해 보세요.", "서버·소프트웨어"),
    (1, "Tomcat 쪽을 먼저 살펴보는 건 어떨까요, 천천히요.", "서버·소프트웨어"),
    (1, "먼저 `curl` 로 증상을 확인해 보면 좋을 것 같아요.", "명령어"),
    (1, "요청이 가는 길에서 무언가 멈춰 있는 곳을 찾아보세요.", "원인을 직접"),
    (2, "WAS 서버 안에서 서비스가 멈춘 상태인지 확인해 보세요.", "원인을 직접"),
    (2, "WAS에서 `systemctl status tomcat10` 를 확인해 보세요, 그렇게요.", "명령어"),
    (3, "WAS에서 상태를 확인해 보세요. 출력도 잘 읽어 보시고요.", "백틱"),
])
def test_bad_hints_are_rejected_by_level(level, text, word):
    ctx, _ = ctx_for(Mission01, level)
    assert word in check_hint(text, ctx)


@pytest.mark.parametrize("text", [
    "WAS에서 `systemctl start tomcat10` 을 실행해 보세요, 그러면 돼요.",
    "WAS에서 `systemctl restart tomcat10` 해 보세요, 아마 될 거예요.",
    "WAS에서 `service tomcat10 start` 를 해 보세요, 간단해요.",
    "Tomcat을 다시 시작해 보세요. `systemctl status tomcat10` 도 같이요.",
])
def test_recovery_commands_never_pass_at_level3_mission01(text):
    ctx, _ = ctx_for(Mission01, 3)
    assert "복구 방법" in check_hint(text, ctx)


def test_level3_commands_are_actually_tested_in_the_simulator():
    ctx, _ = ctx_for(Mission01, 3)
    assert "실행할 수 없는" in check_hint("WAS에서 `ls -la` 를 실행해 보세요, 그러면 보여요.", ctx)
    # 정규식에 안 걸려도 '상태를 바꾸는 명령'이면 막힘
    assert "상태를 바꾸는" in check_hint("WEB에서 `systemctl stop nginx` 를 실행해 보세요, 어떨까요.", ctx)
    # 확인용 명령은 통과
    assert check_hint("WEB에서 `curl http://192.168.111.100` 로 증상을 확인해 보세요, 지금이요.", ctx) is None
    assert check_hint("WAS에서 `ss -tulnp` 를 실행해서 열려 있는 포트를 살펴보세요, 천천히요.", ctx) is None


def test_placeholder_commands_are_rejected_as_not_runnable():
    # 실제로 AI가 한 번 이렇게 써서 실패했던 사례: <WAS의 IP> 같은 자리표시자
    ctx, _ = ctx_for(Mission02, 3)
    assert "실행할 수 없는" in check_hint("WEB에서 `curl http://<WAS의 IP>:8080` 을 실행해 보세요, 천천히요.", ctx)
    assert check_hint("WEB에서 `curl http://192.168.111.200:8080` 을 실행해 보세요, 천천히요.", ctx) is None


def test_context_gives_real_server_ips_so_commands_can_be_complete():
    ctx, _ = ctx_for(Mission01, 3)
    assert ctx.payload["servers"]["WAS"]["ip"] == "192.168.111.200"


def test_hint_length_limits():
    ctx, _ = ctx_for(Mission01, 1)
    assert "길이" in check_hint("짧아요", ctx)
    assert "길이" in check_hint("가" * 501, ctx)


# ---------------------------------------------------------------- 미션 2 규칙
def test_mission02_rules():
    c3, _ = ctx_for(Mission02, 3)
    assert check_hint("WAS에서 `ufw status numbered` 를 실행해서, 규칙의 순서를 살펴보세요, 천천히요.", c3) is None
    assert check_hint("WAS에서 `tail -n 5 /var/log/ufw.log` 를 실행해서 기록을 살펴보세요, 천천히요.", c3) is None
    for bad in ["WAS에서 `ufw delete 2` 를 실행해 보세요, 해결돼요.", "WAS에서 `ufw disable` 을 해 보세요, 되긴 해요.",
                "WAS에서 `ufw status` 를 본 다음, 규칙을 삭제해 보세요, 그러면 돼요."]:
        assert check_hint(bad, c3) is not None, bad
    c2, _ = ctx_for(Mission02, 2)
    assert check_hint("WAS 서버의 방화벽 쪽 설정을 한 번 살펴보면 좋겠어요, 천천히요.", c2) is None  # '영역' 안내는 허용
    assert "원인을 직접" in check_hint("WAS의 방화벽이 WEB을 막고 있는 규칙이 있는지 보세요.", c2)
    c1, _ = ctx_for(Mission02, 1)
    assert "서버·소프트웨어" in check_hint("방화벽 쪽을 먼저 살펴보세요, 차근차근 해 보세요.", c1)


# ---------------------------------------------------------------- 입력(AI에게 가는 정보)
def test_context_has_progress_log_previous_hints_and_a_state_copy():
    s = Session(Mission01())
    s.run("WEB", "curl http://192.168.111.100")
    s.add_hint(1, "첫 번째 힌트였어요, 방향 안내예요.")
    ctx = build_hint_context(s, 2)
    p = ctx.payload
    assert p["hint_level"] == 2 and p["real_root_cause"] == Mission01.root_cause
    assert [e["command"] for e in p["action_log"]] == ["curl http://192.168.111.100"]
    assert p["previous_hints"] == [{"level": 1, "text": "첫 번째 힌트였어요, 방향 안내예요."}]
    assert p["progress"]["root_cause_directly_checked"] is False
    ctx.state_snapshot.running["tomcat10"] = True  # 복사본이라 실제 상태에 영향 없음
    assert s.state.running["tomcat10"] is False


def test_context_with_no_commands_says_so():
    ctx, _ = ctx_for(Mission01, 1)
    assert ctx.payload["action_log"] == [] and "아직 실행한 명령어가 없습니다" in ctx.payload["action_log_note"]


# ---------------------------------------------------------------- 모델 호출(가짜 클라이언트)
def fake_client(*texts):
    calls, queue = [], list(texts)

    def create(**kw):
        calls.append(kw)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=queue.pop(0))])

    ns = SimpleNamespace(beta=SimpleNamespace(messages=SimpleNamespace(create=create)),
                         messages=SimpleNamespace(create=create))
    return ns, calls


def out(text):
    return json.dumps({"hint": text}, ensure_ascii=False)


def test_generate_hint_success_uses_low_effort_and_gets_context(monkeypatch):
    client, calls = fake_client(out(M1_OK[1]))
    monkeypatch.setattr(hint_mod, "_client", lambda: client)
    ctx, _ = ctx_for(Mission01, 1)
    assert generate_hint(ctx) == M1_OK[1]
    kw = calls[0]
    assert kw["output_config"]["effort"] == "low" and kw["output_config"]["format"]["type"] == "json_schema"
    assert kw["fallbacks"] == "default" and "temperature" not in kw
    assert "복구 명령어" in kw["system"] and "비공개 정보" in kw["system"]
    assert "hint_level" in kw["messages"][0]["content"]


def test_generate_hint_retries_with_reason_when_rule_is_broken(monkeypatch):
    bad = "WAS에서 `systemctl start tomcat10` 을 실행해 보세요, 그러면 돼요."
    client, calls = fake_client(out(bad), out(M1_OK[3]))
    monkeypatch.setattr(hint_mod, "_client", lambda: client)
    ctx, _ = ctx_for(Mission01, 3)
    assert generate_hint(ctx) == M1_OK[3]
    assert len(calls) == 2 and "규칙을 어겼습니다" in calls[1]["messages"][0]["content"]


def test_generate_hint_never_returns_a_rule_breaking_hint(monkeypatch):
    bad = "WAS에서 `systemctl start tomcat10` 을 실행해 보세요, 그러면 돼요."
    client, calls = fake_client(out(bad), out(bad), out(bad))
    monkeypatch.setattr(hint_mod, "_client", lambda: client)
    ctx, _ = ctx_for(Mission01, 3)
    with pytest.raises(AIError) as e:
        generate_hint(ctx)
    assert "차감되지 않았어요" in e.value.message and len(calls) == 3


def test_generate_hint_retries_on_broken_json(monkeypatch):
    client, calls = fake_client("깨진 응답", out(M1_OK[2]))
    monkeypatch.setattr(hint_mod, "_client", lambda: client)
    ctx, _ = ctx_for(Mission01, 2)
    assert generate_hint(ctx) == M1_OK[2] and len(calls) == 2


# ---------------------------------------------------------------- API
@pytest.fixture
def api():
    main.SESSIONS.clear()
    c = TestClient(main.app)
    sid = c.post("/api/sessions", json={"mission_id": "mission01"}).json()["sid"]
    return c, sid


def cmd(c, sid, server, command):
    return c.post(f"/api/sessions/{sid}/command", json={"server": server, "command": command}).json()


def ask(c, sid):
    return c.post(f"/api/sessions/{sid}/hint")


def test_three_hints_in_order_then_limit(api, monkeypatch):
    c, sid = api
    seen = []
    monkeypatch.setattr(main, "generate_hint", lambda ctx: seen.append(ctx) or f"{ctx.level}단계 힌트 문장이에요.")
    for n in (1, 2, 3):
        v = ask(c, sid).json()
        assert [h["level"] for h in v["hints"]] == list(range(1, n + 1))
        assert v["progress"]["hints_used"] == n and v["hint_max"] == MAX_HINTS
    assert [x.level for x in seen] == [1, 2, 3]
    assert [h["text"] for h in seen[2].payload["previous_hints"]] == ["1단계 힌트 문장이에요.", "2단계 힌트 문장이에요."]
    r = ask(c, sid)
    assert r.status_code == 409 and "모두 사용" in r.json()["detail"]
    assert len(c.get(f"/api/sessions/{sid}").json()["hints"]) == 3  # 새로고침해도 유지


def test_failed_hint_is_not_counted(api, monkeypatch):
    c, sid = api

    def boom(ctx):
        raise AIError("알맞은 힌트를 만들지 못했어요.", 502)

    monkeypatch.setattr(main, "generate_hint", boom)
    r = ask(c, sid)
    assert r.status_code == 502 and "알맞은 힌트" in r.json()["detail"]
    v = c.get(f"/api/sessions/{sid}").json()
    assert v["hints"] == [] and v["progress"]["hints_used"] == 0
    monkeypatch.setattr(main, "generate_hint", lambda ctx: f"{ctx.level}단계 힌트 문장이에요.")
    assert ask(c, sid).json()["hints"][0]["level"] == 1  # 실패 뒤에도 1단계부터 다시 받을 수 있음


def test_unexpected_error_is_hidden_and_not_counted(api, monkeypatch):
    c, sid = api
    monkeypatch.setattr(main, "generate_hint", lambda ctx: 1 / 0)
    r = ask(c, sid)
    assert r.status_code == 500 and "division" not in r.text
    assert c.get(f"/api/sessions/{sid}").json()["hints"] == []


def test_no_key_gives_setup_guide(api, monkeypatch):
    c, sid = api
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    r = ask(c, sid)
    assert r.status_code == 503 and ".env" in r.json()["detail"]
    assert c.get(f"/api/sessions/{sid}").json()["hints"] == []


def test_no_hints_after_completion(api, monkeypatch):
    c, sid = api
    for server, command in [("WAS", "systemctl start tomcat10"), ("WEB", "curl 192.168.111.200:8080"),
                            ("WEB", "curl 192.168.111.100")]:
        cmd(c, sid, server, command)
    monkeypatch.setattr(main, "generate_hint", lambda ctx: "호출되면 안 돼요, 이 문장은요.")
    r = ask(c, sid)
    assert r.status_code == 409 and "정상화를 마쳤어요" in r.json()["detail"]


def test_reset_clears_hints(api, monkeypatch):
    c, sid = api
    monkeypatch.setattr(main, "generate_hint", lambda ctx: f"{ctx.level}단계 힌트 문장이에요.")
    ask(c, sid)
    v = c.post(f"/api/sessions/{sid}/reset").json()
    assert v["hints"] == [] and v["progress"]["hints_used"] == 0
    assert ask(c, sid).json()["hints"][0]["level"] == 1


def test_reset_during_generation_discards_the_hint(api, monkeypatch):
    c, sid = api

    def gen(ctx):
        main.SESSIONS[sid].reset()  # AI가 힌트를 만드는 동안 사용자가 초기화한 상황
        return "초기화 전에 만든 힌트 문장이에요."

    monkeypatch.setattr(main, "generate_hint", gen)
    r = ask(c, sid)
    assert r.status_code == 409 and "초기화" in r.json()["detail"]
    assert c.get(f"/api/sessions/{sid}").json()["hints"] == []


def test_in_progress_flag_blocks_double_requests(api, monkeypatch):
    c, sid = api
    main.SESSIONS[sid].hint_in_progress = True
    monkeypatch.setattr(main, "generate_hint", lambda ctx: "호출되면 안 돼요, 이 문장은요.")
    assert ask(c, sid).status_code == 409
    main.SESSIONS[sid].hint_in_progress = False


def test_hint_text_and_cause_do_not_leak_other_data(api, monkeypatch):
    c, sid = api
    monkeypatch.setattr(main, "generate_hint", lambda ctx: "요청이 지나가는 길을 따라가 보세요, 천천히요.")
    text = ask(c, sid).text
    assert Mission01.root_cause not in text and Mission01.correct_recovery not in text


def test_mission02_hint_context_uses_mission02_cause():
    s = Session(Mission02())
    ctx = build_hint_context(s, 1)
    assert ctx.payload["real_root_cause"] == Mission02.root_cause and ctx.payload["mission"]["title"] == "연결되지 않는 서버"


# ---------------------------------------------------------------- 리뷰에 반영
def test_review_input_includes_hints_given_and_count():
    s = Session(Mission01())
    s.run("WEB", "curl http://192.168.111.100")
    s.add_hint(1, "첫 번째 힌트 문장이에요, 방향이에요.")
    s.run("WAS", "systemctl status tomcat10")
    s.add_hint(2, "두 번째 힌트 문장이에요, 영역이에요.")
    pl = build_review_input(s)
    assert pl["stats"]["hints_used"] == 2
    assert pl["hints_given"] == [
        {"level": 1, "text": "첫 번째 힌트 문장이에요, 방향이에요.", "given_after_command_seq": 1},
        {"level": 2, "text": "두 번째 힌트 문장이에요, 영역이에요.", "given_after_command_seq": 2},
    ]
