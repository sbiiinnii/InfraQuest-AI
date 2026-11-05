import pytest
from fastapi.testclient import TestClient

import main
from ai.review import build_review_input
from engine.session import Session
from scenarios.mission03 import Mission03

WEB_IP, WAS_IP, DB_IP = "192.168.111.100", "192.168.111.200", "192.168.111.210"


@pytest.fixture
def s():
    return Session(Mission03())


def run(s, server, cmd):
    return s.run(server, cmd)


def verify(s):
    run(s, "WEB", f"curl http://{WAS_IP}:8080")
    run(s, "WEB", f"curl http://{WEB_IP}")


# ---------------------------------------------------------------- 증상: 502가 아니라 500
def test_symptom_is_500_not_502(s):
    out = run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    assert "500" in out and "Internal Server Error" in out and "502" not in out
    assert "Apache Tomcat" in out  # 오류 페이지를 만든 쪽은 Nginx가 아니라 Tomcat


def test_headers_show_nginx_passes_through_tomcat_error(s):
    out = run(s, "WEB", f"curl -i http://{WEB_IP}")["output"]
    assert out.startswith("HTTP/1.1 500 Internal Server Error") and "Server: nginx" in out
    direct = run(s, "WEB", f"curl -I http://{WAS_IP}:8080")["output"]
    assert direct.startswith("HTTP/1.1 500") and "nginx" not in direct


def test_was_direct_request_also_fails_with_500(s):
    assert "500" in run(s, "WEB", f"curl http://{WAS_IP}:8080")["output"]
    assert "500" in run(s, "WAS", "curl http://localhost:8080")["output"]


def test_nginx_has_no_error_so_look_further_back(s):
    # 502가 아니므로 Nginx 오류 로그에는 아무것도 남지 않습니다
    assert run(s, "WEB", "cat /var/log/nginx/error.log")["output"] == ""
    run(s, "WEB", f"curl http://{WEB_IP}")
    assert run(s, "WEB", "cat /var/log/nginx/error.log")["output"] == ""


# ---------------------------------------------------------------- WAS는 멀쩡하다
def test_was_service_and_port_are_healthy(s):
    assert "active (running)" in run(s, "WAS", "systemctl status tomcat10")["output"]
    assert ":8080" in run(s, "WAS", "ss -tulnp")["output"]


def test_tomcat_log_has_seeded_db_errors_and_grows(s):
    first = run(s, "WAS", "cat /var/log/tomcat10/catalina.out")["output"]
    assert first.count("SQLNonTransientConnectionException") == 4
    assert f"host={DB_IP}" in first and "port=3306" in first and "Connection refused" in first
    run(s, "WEB", f"curl http://{WEB_IP}")
    assert run(s, "WAS", "cat /var/log/tomcat10/catalina.out")["output"].count("SQLNonTransientConnectionException") == 5


def test_tomcat_log_exists_only_on_was(s):
    assert "No such file" in run(s, "WEB", "cat /var/log/tomcat10/catalina.out")["output"]
    assert "No such file" in run(s, "DB", "cat /var/log/tomcat10/catalina.out")["output"]
    assert "catalina.out" in run(s, "WAS", "help")["output"]


def test_health_checks_do_not_write_tomcat_log(s):
    before = run(s, "WAS", "cat /var/log/tomcat10/catalina.out")["output"].count("SEVERE")
    for _ in range(5):
        run(s, "WAS", "hostname")
    assert run(s, "WAS", "cat /var/log/tomcat10/catalina.out")["output"].count("SEVERE") == before


# ---------------------------------------------------------------- 원인은 DB
def test_db_side_shows_mariadb_down(s):
    assert "inactive (dead)" in run(s, "DB", "systemctl status mariadb")["output"]
    assert "3306" not in run(s, "DB", "ss -tulnp")["output"]
    assert "Stopped mariadb.service" in run(s, "DB", "journalctl -u mariadb")["output"]


def test_was_cannot_reach_db(s):
    e = run(s, "WAS", f"curl http://{DB_IP}:3306")
    assert e["exit_code"] == 7 and "Couldn't connect to server" in e["output"]


# ---------------------------------------------------------------- 진단 판정
def test_diagnosis_requires_checking_the_db_itself(s):
    run(s, "WEB", f"curl http://{WEB_IP}")
    run(s, "WAS", "systemctl status tomcat10")
    run(s, "WAS", "cat /var/log/tomcat10/catalina.out")
    run(s, "WAS", f"curl http://{DB_IP}:3306")
    p = s.progress()
    assert p["diagnosed"] is False  # 단서만 모았고 DB를 직접 확인하지는 않음
    assert len(p["evidence"]) == 4
    run(s, "DB", "systemctl status mariadb")
    assert s.progress()["diagnosed"] is True


@pytest.mark.parametrize("server,cmd", [("DB", "systemctl status mariadb"), ("DB", "ss -tulnp"),
                                        ("DB", "journalctl -u mariadb")])
def test_each_db_check_counts_as_root_cause_evidence(s, server, cmd):
    run(s, server, cmd)
    assert s.progress()["diagnosed"] is True


# ---------------------------------------------------------------- 잘못된 조치 / 올바른 복구
def test_restarting_tomcat_or_nginx_does_not_fix(s):
    run(s, "WAS", "systemctl restart tomcat10")
    run(s, "WEB", "systemctl restart nginx")
    assert "500" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    p = s.progress()
    assert p["recovered"] is False and len(p["other_actions"]) == 2


def test_starting_mariadb_fixes_the_service(s):
    run(s, "DB", "systemctl status mariadb")
    run(s, "DB", "systemctl start mariadb")
    assert "InfraQuest Shop" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    assert "InfraQuest Shop" in run(s, "WAS", "curl http://localhost:8080")["output"]
    assert s.progress()["recovered"] is True


def test_restart_mariadb_also_counts_as_recovery(s):
    run(s, "DB", "systemctl restart mariadb")
    assert s.progress()["recovered"] is True


def test_recovery_is_not_complete_until_verified(s):
    run(s, "DB", "systemctl start mariadb")
    assert s.progress()["completed"] is False
    run(s, "WEB", f"curl http://{WAS_IP}:8080")
    assert s.progress()["completed"] is False  # WEB 경유 확인이 아직 없음
    run(s, "WEB", f"curl http://{WEB_IP}")
    p = s.progress()
    assert p["completed"] is True and p["verification"] == {"was_direct": True, "web": True}


def test_verification_before_recovery_does_not_count(s):
    verify(s)  # 장애 중에 확인한 것(500)은 검증이 아님
    run(s, "DB", "systemctl start mariadb")
    assert s.progress()["completed"] is False


# ---------------------------------------------------------------- 다른 미션에는 영향 없음
def test_missions_one_and_two_are_unchanged_by_db_rule():
    from scenarios.mission01 import Mission01
    from scenarios.mission02 import Mission02
    for m in (Mission01(), Mission02()):
        st = m.initial_state()
        assert st.app_status() == 200 and st.tomcat_log == []


# ---------------------------------------------------------------- AI 입력 / API
def test_review_input_has_cause_and_followups(s):
    run(s, "DB", "systemctl start mariadb")
    verify(s)
    pl = build_review_input(s)
    assert pl["real_root_cause"] == Mission03.root_cause and "MariaDB" in pl["real_root_cause"]
    ids = [f["id"] for f in pl["available_followups"]]
    assert ids == ["mission01", "mission02"]
    assert "mariadb" not in str(pl["available_followups"]).lower()


def test_mission_list_includes_mission03_without_spoilers():
    c = TestClient(main.app)
    listed = {m["id"]: m for m in c.get("/api/missions").json()}
    assert "mission03" in listed and listed["mission03"]["number"] == 3
    text = listed["mission03"]["title"] + listed["mission03"]["summary"]  # 분류 이름(WEB/WAS/DB)은 모든 미션 공통이라 제외
    for spoiler in ("DB", "MariaDB", "mariadb", "500", "데이터베이스"):
        assert spoiler not in text


def test_api_session_for_mission03_hides_cause():
    c = TestClient(main.app)
    sid = c.post("/api/sessions", json={"mission_id": "mission03"}).json()["sid"]
    c.post(f"/api/sessions/{sid}/command", json={"server": "WEB", "command": f"curl http://{WEB_IP}"})
    text = c.get(f"/api/sessions/{sid}").text
    assert Mission03.root_cause not in text and Mission03.correct_recovery not in text
    assert "열렸지만 오류가 나는 웹" in text


def test_hint_rules_block_recovery_commands_and_early_cause_words():
    import re
    forbidden_all = Mission03.hint_forbidden_all
    for bad in ("DB에서 systemctl start mariadb 를 해 보세요", "MariaDB를 다시 시작해 보세요", "데이터베이스를 켜 보세요"):
        assert any(re.search(p, bad, re.I) for p in forbidden_all), bad
    assert not any(re.search(p, "DB 서버의 서비스 상태를 살펴보세요", re.I) for p in forbidden_all)
    assert any(re.search(p, "서비스가 중단되어 있어요", re.I) for p in Mission03.hint_forbidden_early)
