import pytest
from fastapi.testclient import TestClient

import main
from engine.session import Session
from scenarios.mission01 import Mission01
from scenarios.mission02 import Mission02
from scenarios.mission03 import Mission03

WEB_IP, WAS_IP, DB_IP = "192.168.111.100", "192.168.111.200", "192.168.111.210"


def texts(s, server):
    return [(o["text"], o["ok"], o["stale"]) for o in s.public_observed()[server]]


# ---------------------------------------------------------------- 점검 전에는 아무것도 알려 주지 않음
@pytest.mark.parametrize("mission", [Mission01, Mission02, Mission03])
def test_nothing_is_shown_before_checking(mission):
    s = Session(mission())
    assert s.public_observed() == {"WEB": [], "WAS": [], "DB": []}


def test_only_the_checked_server_is_shown():
    s = Session(Mission01())
    s.run("WAS", "systemctl status tomcat10")
    assert texts(s, "WAS") == [("tomcat10 중단", False, False)]
    assert texts(s, "WEB") == [] and texts(s, "DB") == []  # 점검하지 않은 서버는 비어 있어야 함


def test_unsupported_and_unrelated_commands_show_nothing():
    s = Session(Mission01())
    for server, cmd in [("WAS", "rm -rf /"), ("WAS", "hostname"), ("WAS", "help"), ("WAS", "cat /var/log/ufw.log"),
                        ("WAS", "systemctl status nope"), ("WEB", "curl http://nowhere.example")]:
        s.run(server, cmd)
    assert s.public_observed() == {"WEB": [], "WAS": [], "DB": []}


# ---------------------------------------------------------------- 명령어별 결과
def test_port_check_uses_each_servers_own_port():
    s = Session(Mission01())
    s.run("WAS", "ss -tulnp")
    s.run("DB", "ss -tulnp")
    assert texts(s, "WAS") == [("8080번 포트 닫힘", False, False)]
    assert texts(s, "DB") == [("3306번 포트 열림", True, False)]


def test_curl_results_attach_to_the_target_server():
    s = Session(Mission01())
    s.run("WEB", f"curl http://{WEB_IP}")
    s.run("WEB", f"curl http://{WAS_IP}:8080")
    assert texts(s, "WEB") == [("80번 요청 오류(502)", False, False)]
    assert texts(s, "WAS") == [("WEB에서 8080번 연결 거부", False, False)]


def test_mission02_shows_service_ok_but_web_blocked_without_naming_firewall():
    s = Session(Mission02())
    s.run("WAS", "systemctl status tomcat10")
    s.run("WAS", "curl http://localhost:8080")
    s.run("WEB", f"curl http://{WAS_IP}:8080")
    got = texts(s, "WAS")
    assert ("tomcat10 실행 중", True, False) in got
    assert ("8080번 요청 정상(200)", True, False) in got
    assert ("WEB에서 8080번 연결 거부", False, False) in got
    assert not any("방화벽" in t or "ufw" in t for t, _, _ in got)  # 아직 방화벽을 점검하지 않았으니 알려 주지 않음


def test_ufw_status_is_shown_only_after_checking_it():
    s = Session(Mission02())
    s.run("WAS", "ufw status")
    assert texts(s, "WAS") == [("차단 규칙 있음", False, False)]
    s.run("WEB", "ufw status")
    assert texts(s, "WEB") == [("방화벽 꺼짐", True, False)]


def test_mission03_chain_is_shown_step_by_step():
    s = Session(Mission03())
    s.run("WEB", f"curl http://{WEB_IP}")
    assert texts(s, "WEB") == [("80번 요청 오류(500)", False, False)]
    assert texts(s, "DB") == []  # DB가 원인이라는 것은 직접 점검하기 전까지 알려 주지 않음
    s.run("WAS", f"curl http://{DB_IP}:3306")
    assert texts(s, "DB") == [("WAS에서 3306번 연결 거부", False, False)]
    s.run("DB", "systemctl status mariadb")
    assert ("mariadb 중단", False, False) in texts(s, "DB")


# ---------------------------------------------------------------- 조치 후에는 '다시 확인 필요'
def test_results_become_stale_after_a_change_and_refresh_when_rechecked():
    s = Session(Mission01())
    s.run("WAS", "systemctl status tomcat10")
    s.run("WEB", f"curl http://{WEB_IP}")
    s.run("WAS", "systemctl start tomcat10")
    assert texts(s, "WAS") == [("tomcat10 중단", False, True)]  # 이미 고쳤지만 확인 전이라 옛 결과임을 표시
    assert texts(s, "WEB") == [("80번 요청 오류(502)", False, True)]
    s.run("WAS", "systemctl status tomcat10")
    assert texts(s, "WAS") == [("tomcat10 실행 중", True, False)]
    assert texts(s, "WEB") == [("80번 요청 오류(502)", False, True)]  # 점검한 서버만 갱신됨


def test_a_command_that_changes_nothing_does_not_make_results_stale():
    s = Session(Mission01())
    s.run("WAS", "systemctl status tomcat10")
    s.run("WEB", "systemctl start nginx")  # 이미 실행 중이라 바뀐 것이 없음
    assert texts(s, "WAS") == [("tomcat10 중단", False, False)]


def test_same_check_updates_in_place_instead_of_piling_up():
    s = Session(Mission01())
    for _ in range(3):
        s.run("WAS", "systemctl status tomcat10")
    assert len(texts(s, "WAS")) == 1


def test_reset_clears_observations():
    s = Session(Mission01())
    s.run("WAS", "systemctl status tomcat10")
    s.reset()
    assert s.public_observed() == {"WEB": [], "WAS": [], "DB": []}


# ---------------------------------------------------------------- API
def test_api_exposes_observed_without_internal_facts():
    c = TestClient(main.app)
    sid = c.post("/api/sessions", json={"mission_id": "mission01"}).json()["sid"]
    d = c.post(f"/api/sessions/{sid}/command", json={"server": "WAS", "command": "systemctl status tomcat10"}).json()
    assert d["observed"]["WAS"] == [{"ok": False, "text": "tomcat10 중단", "stale": False}]
    assert d["observed"]["WEB"] == [] and d["observed"]["DB"] == []
    assert "facts" not in str(d)
