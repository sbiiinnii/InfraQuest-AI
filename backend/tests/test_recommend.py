import pytest
from fastapi.testclient import TestClient

import main
from engine.recommend import recommend
from engine.session import Session
from scenarios import MISSIONS

WEB_IP, WAS_IP = "192.168.111.100", "192.168.111.200"
VERIFY = [("WEB", f"curl http://{WAS_IP}:8080"), ("WEB", f"curl http://{WEB_IP}")]


def play(mission, steps):
    s = Session(MISSIONS[mission])
    for server, cmd in steps:
        s.run(server, cmd)
    assert s.progress()["completed"] is True, "테스트 준비 실패: 미션이 끝나지 않았어요"
    return s


# 원인을 직접 확인하고, 필요한 조치만 하고, 검증까지 마친 '깔끔한' 풀이
CLEAN = {
    "mission01": [("WEB", f"curl http://{WEB_IP}"), ("WAS", "systemctl status tomcat10"),
                  ("WAS", "systemctl start tomcat10"), *VERIFY],
    "mission02": [("WEB", f"curl http://{WEB_IP}"), ("WAS", "ufw status numbered"),
                  ("WAS", "ufw delete 2"), *VERIFY],
    "mission03": [("WEB", f"curl http://{WEB_IP}"), ("DB", "systemctl status mariadb"),
                  ("DB", "systemctl start mariadb"), *VERIFY],
}


def clean(mission):
    return play(mission, CLEAN[mission])


# ---------------------------------------------------------------- 약점이 없을 때: 아직 안 푼 다음 미션
def test_clean_run_recommends_the_next_unsolved_mission():
    r = recommend(clean("mission01"), set())
    assert r["kind"] == "next" and r["mission"]["id"] == "mission02" and r["retry"] is False


def test_clean_run_skips_missions_already_done():
    r = recommend(clean("mission01"), {"mission02"})
    assert r["mission"]["id"] == "mission03"


def test_clean_run_wraps_around_to_an_earlier_unsolved_mission():
    assert recommend(clean("mission03"), set())["mission"]["id"] == "mission01"
    assert recommend(clean("mission03"), {"mission01"})["mission"]["id"] == "mission02"


def test_all_done_says_so_honestly_without_inventing_a_mission():
    r = recommend(clean("mission02"), {"mission01", "mission02", "mission03"})
    assert r["kind"] == "all_done" and r["mission"] is None and "준비 중" in r["reason"]


def test_current_mission_counts_as_done_even_if_browser_did_not_say_so():
    r = recommend(clean("mission01"), set())
    assert r["mission"]["id"] != "mission01"


# ---------------------------------------------------------------- 약점별 추천
def test_dangerous_action_recommends_safe_practice_and_shows_the_action():
    s = play("mission02", [("WEB", f"curl http://{WEB_IP}"), ("WAS", "ufw status"), ("WAS", "ufw disable"), *VERIFY])
    r = recommend(s, set())
    assert r["code"] == "risky" and r["mission"]["id"] == "mission02" and r["retry"] is True  # 같은 미션 다시
    assert any("ufw disable" in e for e in r["evidence"])  # 실제로 한 조치가 근거로 보여야 함


def test_help_from_hints_recommends_doing_the_same_mission_again():
    s = clean("mission01")
    for lv in (1, 2, 3):
        s.add_hint(lv, f"{lv}단계 힌트")
    r = recommend(s, {"mission02"})
    assert r["code"] == "helped" and r["retry"] is True and r["mission"]["id"] == "mission01"
    assert r["evidence"] == ["AI 힌트를 3개 썼어요."]


def test_viewing_the_solution_is_named_in_the_evidence():
    s = clean("mission01")
    s.view_solution()
    r = recommend(s, set())
    assert r["code"] == "helped" and "정답 해설을 보고 풀었어요." in r["evidence"]


def test_two_hints_alone_is_not_treated_as_heavy_help():
    s = clean("mission01")
    s.add_hint(1, "a")
    s.add_hint(2, "b")
    assert recommend(s, set())["code"] == "clean"


def test_recovering_without_checking_the_cause_recommends_tracing_practice():
    s = play("mission01", [("WAS", "systemctl start tomcat10"), *VERIFY])  # 원인 확인 없이 바로 조치
    r = recommend(s, set())
    assert r["code"] == "no_root_check" and r["mission"]["id"] == "mission03" and r["retry"] is False


def test_many_unsupported_commands_recommend_the_basics_mission():
    s = Session(MISSIONS["mission03"])
    for cmd in ["rm -rf /", "top", "vim a", "ping 1.1.1.1"]:
        s.run("WEB", cmd)
    for server, cmd in CLEAN["mission03"]:
        s.run(server, cmd)
    r = recommend(s, set())
    assert r["code"] == "commands" and r["mission"]["id"] == "mission01" and r["retry"] is False
    assert r["evidence"] == ["지원하지 않는 명령어를 4번 입력했어요."]


def test_several_unrelated_actions_recommend_precise_fixing_and_flag_already_done():
    steps = [("WEB", f"curl http://{WEB_IP}"), ("WAS", "systemctl restart tomcat10"), ("WEB", "systemctl restart nginx"),
             ("DB", "systemctl status mariadb"), ("DB", "systemctl start mariadb"), *VERIFY]
    r = recommend(play("mission03", steps), set())
    assert r["code"] == "extra_actions" and r["mission"]["id"] == "mission02" and r["already_done"] is False
    assert recommend(play("mission03", steps), {"mission02"})["already_done"] is True


def test_priority_danger_beats_help():
    s = play("mission02", [("WAS", "ufw status"), ("WAS", "ufw disable"), *VERIFY])
    s.view_solution()
    assert recommend(s, set())["code"] == "risky"


# ---------------------------------------------------------------- 성질
@pytest.mark.parametrize("mission", ["mission01", "mission02", "mission03"])
def test_same_record_always_gives_the_same_recommendation(mission):
    s = clean(mission)
    assert recommend(s, {"mission01"}) == recommend(s, {"mission01"})


def test_recommendation_text_never_reveals_other_missions_causes():
    # 추천 화면에 나오는 미션 소개는 원인(방화벽·DB 중단 등)을 알려 주면 안 됩니다.
    secrets = ["방화벽", "ufw", "REJECT", "mariadb", "MariaDB", "데이터베이스", "DB 서버", "Tomcat", "tomcat", "중단"]
    for m in MISSIONS.values():
        leaked = [w for w in secrets if w in m.title + m.training]
        assert not leaked, (m.id, leaked)


def test_training_line_exists_for_every_mission():
    assert all(m.training for m in MISSIONS.values())


# ---------------------------------------------------------------- API
@pytest.fixture
def api():
    return TestClient(main.app)


def finish_via_api(api, mission):
    sid = api.post("/api/sessions", json={"mission_id": mission}).json()["sid"]
    for server, cmd in CLEAN[mission]:
        api.post(f"/api/sessions/{sid}/command", json={"server": server, "command": cmd})
    return sid


def test_api_blocked_before_completion(api):
    sid = api.post("/api/sessions", json={"mission_id": "mission01"}).json()["sid"]
    r = api.get(f"/api/sessions/{sid}/recommendation")
    assert r.status_code == 409 and "완료" in r.json()["detail"]


def test_api_returns_recommendation_using_done_list(api):
    sid = finish_via_api(api, "mission01")
    r = api.get(f"/api/sessions/{sid}/recommendation", params={"done": "mission01,mission02"}).json()
    assert r["mission"]["id"] == "mission03" and r["kind"] == "next"
    assert set(r["mission"]) == {"id", "number", "title", "training", "difficulty", "minutes"}  # 원인 정보 없음


def test_api_ignores_unknown_or_empty_done_ids(api):
    sid = finish_via_api(api, "mission01")
    r = api.get(f"/api/sessions/{sid}/recommendation", params={"done": ",,nope,../etc,mission02"}).json()
    assert r["mission"]["id"] == "mission03"
    assert api.get(f"/api/sessions/{sid}/recommendation").json()["mission"]["id"] == "mission02"


def test_api_unknown_session_is_404(api):
    assert api.get("/api/sessions/nope/recommendation").status_code == 404


def test_api_works_without_any_ai_call(api, monkeypatch):
    # AI 리뷰가 고장 나도 추천은 나와야 합니다.
    def boom(*a, **k):
        raise AssertionError("추천이 AI를 불렀어요")
    monkeypatch.setattr(main, "generate_review", boom)
    monkeypatch.setattr(main, "generate_hint", boom)
    sid = finish_via_api(api, "mission02")
    assert api.get(f"/api/sessions/{sid}/recommendation").status_code == 200
