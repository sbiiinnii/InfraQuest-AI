import pytest
from fastapi.testclient import TestClient

import main
from ai.review import build_review_input
from engine.session import Session
from scenarios.mission01 import Mission01
from scenarios.mission02 import Mission02

WEB_IP, WAS_IP = "192.168.111.100", "192.168.111.200"


@pytest.fixture
def s():
    return Session(Mission02())


def run(s, server, cmd):
    return s.run(server, cmd)


def verify(s):
    run(s, "WEB", f"curl http://{WAS_IP}:8080")
    run(s, "WEB", f"curl http://{WEB_IP}")


# ---------------------------------------------------------------- 같은 증상
def test_same_symptoms_as_mission01(s):
    assert "502 Bad Gateway" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    e = run(s, "WEB", f"curl http://{WAS_IP}:8080")
    assert e["exit_code"] == 7 and "Couldn't connect to server" in e["output"]
    log = run(s, "WEB", "tail -n 4 /var/log/nginx/error.log")["output"]
    assert log.count("Connection refused") == 4


# ---------------------------------------------------------------- 다른 원인: 서비스는 정상
def test_was_service_is_healthy_so_cause_is_elsewhere(s):
    assert "active (running)" in run(s, "WAS", "systemctl status tomcat10")["output"]
    assert ":8080" in run(s, "WAS", "ss -tulnp")["output"]
    assert "InfraQuest Shop" in run(s, "WAS", "curl http://localhost:8080")["output"]
    assert "InfraQuest Shop" in run(s, "WAS", f"curl http://{WAS_IP}:8080")["output"]  # 자기 자신은 방화벽 무시


def test_only_web_is_blocked_other_servers_can_reach_8080(s):
    # '다른 서버에서는 되는데 WEB에서만 안 된다' → 출발지별 규칙(방화벽)을 의심하게 만드는 단서
    assert "InfraQuest Shop" in run(s, "DB", f"curl http://{WAS_IP}:8080")["output"]
    assert run(s, "WEB", f"curl http://{WAS_IP}:8080")["exit_code"] == 7


def test_starting_tomcat_changes_nothing(s):
    run(s, "WAS", "systemctl start tomcat10")  # 이미 실행 중
    assert "502" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    assert s.progress()["other_actions"] == [] and s.progress()["recovered"] is False


def test_ufw_status_shows_rules_only_on_was(s):
    out = run(s, "WAS", "ufw status")["output"]
    assert "Status: active" in out and "22/tcp" in out and "8080/tcp" in out
    assert "REJECT" in out and WEB_IP in out
    assert run(s, "WEB", "ufw status")["output"] == "Status: inactive"
    assert run(s, "DB", "ufw status")["output"] == "Status: inactive"


def test_ufw_status_numbered_and_verbose(s):
    out = run(s, "WAS", "ufw status numbered")["output"]
    assert "[ 1] 22/tcp" in out and "[ 2] 8080/tcp" in out and "[ 3] 8080/tcp" in out and "REJECT IN" in out
    assert "Default: deny (incoming)" in run(s, "WAS", "ufw status verbose")["output"]


def test_ufw_log_has_seeded_blocks_and_grows_with_new_failures(s):
    first = run(s, "WAS", "cat /var/log/ufw.log")["output"]
    assert first.count("[UFW BLOCK]") == 4 and f"SRC={WEB_IP}" in first and "DPT=8080" in first
    run(s, "WEB", f"curl http://{WEB_IP}")
    assert run(s, "WAS", "cat /var/log/ufw.log")["output"].count("[UFW BLOCK]") == 5


def test_ufw_log_only_where_it_exists(s):
    assert "No such file" in run(s, "WEB", "cat /var/log/ufw.log")["output"]
    m1 = Session(Mission01())
    assert "No such file" in m1.run("WAS", "cat /var/log/ufw.log")["output"]  # 미션 1은 방화벽이 꺼져 있음


def test_health_checks_do_not_write_logs(s):
    before = run(s, "WAS", "cat /var/log/ufw.log")["output"].count("BLOCK")
    for _ in range(5):
        run(s, "WAS", "hostname")  # 명령어마다 내부적으로 상태를 계산하지만 로그가 쌓이면 안 됨
    assert run(s, "WAS", "cat /var/log/ufw.log")["output"].count("BLOCK") == before


# ---------------------------------------------------------------- 진단 판정
def test_diagnosis_requires_firewall_evidence_not_just_ruling_out_tomcat(s):
    run(s, "WAS", "systemctl status tomcat10")
    run(s, "WAS", "ss -tulnp")
    run(s, "WAS", "curl localhost:8080")
    p = s.progress()
    assert p["diagnosed"] is False and len(p["evidence"]) == 3  # 원인 후보를 좁힌 증거는 남지만 진단 완료는 아님
    run(s, "WAS", "ufw status")
    assert s.progress()["diagnosed"] is True


def test_diagnosis_via_ufw_log(s):
    run(s, "WAS", "tail -n 3 /var/log/ufw.log")
    assert s.progress()["diagnosed"] is True


def test_checking_ufw_on_wrong_server_is_not_diagnosis(s):
    run(s, "WEB", "ufw status")
    run(s, "DB", "ufw status")
    assert s.progress()["diagnosed"] is False


def test_mission01_cause_checks_do_not_count_here(s):
    run(s, "WAS", "journalctl -u tomcat10")
    run(s, "WEB", "systemctl status tomcat10")  # 잘못된 서버
    assert s.progress()["diagnosed"] is False


# ---------------------------------------------------------------- 복구 방법별 판정
def test_delete_by_number_fixes_and_completes(s):
    out = run(s, "WAS", "ufw delete 2")["output"]
    assert "Deleting:" in out and "reject from 192.168.111.100 to any port 8080 proto tcp" in out and "Rule deleted" in out
    verify(s)
    p = s.progress()
    assert p["recovered"] and p["completed"] and p["risky_actions"] == []
    assert p["recovery_actions"] == ["WAS에서 `ufw delete 2` 실행"]


def test_delete_by_rule_spec_fixes_even_without_proto(s):
    run(s, "WAS", f"ufw delete reject from {WEB_IP} to any port 8080")
    verify(s)
    assert s.progress()["completed"]


def test_insert_allow_before_block_fixes_safely(s):
    assert "Rule inserted" in run(s, "WAS", f"ufw insert 1 allow from {WEB_IP} to any port 8080 proto tcp")["output"]
    verify(s)
    p = s.progress()
    assert p["completed"] and p["risky_actions"] == []


def test_allow_appended_after_reject_does_not_fix(s):
    assert "Rule added" in run(s, "WAS", f"ufw allow from {WEB_IP} to any port 8080 proto tcp")["output"]
    assert "502" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]  # 첫 번째로 맞는 규칙(REJECT)이 먼저 적용됨
    out = run(s, "WAS", "ufw status numbered")["output"]
    assert out.index("REJECT") < out.index("ALLOW IN    192.168.111.100")
    p = s.progress()
    assert not p["recovered"] and not p["completed"] and len(p["other_actions"]) == 1


def test_inserting_an_existing_rule_is_skipped_like_real_ufw(s):
    assert "Skipping inserting existing rule" in run(s, "WAS", "ufw insert 1 allow 8080/tcp")["output"]
    assert "Skipping adding existing rule" in run(s, "WAS", "ufw allow 8080/tcp")["output"]
    assert "502" in run(s, "WEB", f"curl http://{WEB_IP}")["output"] and s.progress()["other_actions"] == []


def test_deleting_the_allow_rule_instead_does_not_fix(s):
    run(s, "WAS", "ufw delete 3")  # 엉뚱한 규칙(원래 있던 허용 규칙)을 지움
    assert "502" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    p = s.progress()
    assert not p["recovered"] and len(p["other_actions"]) == 1
    run(s, "WAS", "ufw delete 2")  # 차단 규칙까지 지워도 허용 규칙이 없어 기본 차단(응답 없음)
    e = run(s, "WEB", f"curl http://{WAS_IP}:8080")
    assert e["exit_code"] == 28 and not s.progress()["recovered"]


def test_allow_all_8080_inserted_first_fixes_but_is_flagged_broad(s):
    run(s, "WAS", "ufw insert 1 allow 8080")  # 프로토콜 없이 쓰면 기존 규칙과 다른 규칙으로 취급됨
    verify(s)
    p = s.progress()
    assert p["completed"] and len(p["risky_actions"]) == 1 and "모든 출발지" in p["risky_actions"][0]


def test_disable_firewall_fixes_but_is_flagged_risky(s):
    assert "Firewall stopped" in run(s, "WAS", "ufw disable")["output"]
    assert run(s, "WAS", "ufw status")["output"] == "Status: inactive"
    verify(s)
    p = s.progress()
    assert p["completed"] and len(p["risky_actions"]) == 1 and "방화벽 전체를 끄는" in p["risky_actions"][0]


def test_wrong_fix_restarting_services_does_not_help(s):
    run(s, "WAS", "systemctl restart tomcat10")
    run(s, "WEB", "systemctl restart nginx")
    assert "502" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    p = s.progress()
    assert not p["recovered"] and len(p["other_actions"]) == 2


def test_recovery_alone_is_not_completion(s):
    run(s, "WAS", "ufw delete 2")
    assert s.progress()["recovered"] and not s.progress()["completed"]
    run(s, "WEB", f"curl http://{WAS_IP}:8080")
    assert not s.progress()["completed"]


def test_reenabling_block_after_recovery_uncompletes(s):
    run(s, "WAS", "ufw delete 2")
    verify(s)
    assert s.progress()["completed"]
    run(s, "WAS", f"ufw insert 1 reject from {WEB_IP} to any port 8080 proto tcp")
    p = s.progress()
    assert not p["recovered"] and not p["completed"]


# ---------------------------------------------------------------- ufw 명령 자체의 정직한 응답
@pytest.mark.parametrize("cmd,word", [
    ("ufw delete 9", "Could not find rule '9'"),
    ("ufw insert 9 allow 80/tcp", "Invalid position"),
    ("ufw delete allow 9999/tcp", "non-existent"),
    ("ufw allow 22/tcp", "Skipping adding existing rule"),
])
def test_ufw_error_messages_and_no_state_change(s, cmd, word):
    assert word in run(s, "WAS", cmd)["output"]
    assert "REJECT" in run(s, "WAS", "ufw status")["output"]
    assert s.progress()["other_actions"] == []


@pytest.mark.parametrize("cmd", ["ufw allow 99999/tcp", "ufw allow 80/udp", "ufw allow from bad to any port 80",
                                 "ufw app list", "ufw reset", "ufw allow in on eth0 to any port 80"])
def test_unsupported_ufw_forms_are_rejected_honestly(s, cmd):
    e = run(s, "WAS", cmd)
    assert e["supported"] is False and e["output"].startswith("[가상 터미널]")


def test_ufw_enable_disable_reload(s):
    assert "Firewall reloaded" in run(s, "WAS", "ufw reload")["output"]
    assert "not enabled" in run(s, "WEB", "ufw reload")["output"]
    run(s, "WAS", "ufw disable")
    assert "502" not in run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    run(s, "WAS", "ufw enable")
    assert "502" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]  # 규칙이 그대로 살아 있어 다시 차단됨


def test_ufw_changes_on_other_servers_do_not_affect_was(s):
    run(s, "WEB", "ufw allow 80/tcp")
    assert "502" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    assert s.progress()["recovered"] is False


# ---------------------------------------------------------------- 전체 흐름 / 초기화 / 미션 1과의 관계
def test_full_flow_with_evidence_and_hypothesis(s):
    run(s, "WEB", f"curl http://{WEB_IP}")
    run(s, "WAS", "systemctl status tomcat10")
    run(s, "WAS", "curl localhost:8080")
    run(s, "WAS", "ufw status numbered")
    s.submit_hypothesis("Tomcat은 정상이지만 WAS 방화벽이 WEB에서 오는 8080을 거부해서 502가 난다")
    run(s, "WAS", "ufw delete 2")
    verify(s)
    p = s.progress()
    assert p["completed"] and p["diagnosed"] and p["hypothesis_submitted"]
    assert any("방화벽(ufw) 규칙" in e for e in p["evidence"]) and any("정상 실행 중" in e for e in p["evidence"])
    assert p["commands_total"] == 7


def test_reset_restores_firewall_block_and_logs(s):
    run(s, "WAS", "ufw delete 2")
    s.reset()
    assert "502" in run(s, "WEB", f"curl http://{WEB_IP}")["output"]
    assert "REJECT" in run(s, "WAS", "ufw status")["output"]
    assert run(s, "WAS", "cat /var/log/ufw.log")["output"].count("[UFW BLOCK]") == 5  # 시드 4 + 새 실패 1


def test_mission01_still_behaves_the_same_with_ufw_commands():
    m1 = Session(Mission01())
    assert m1.run("WAS", "ufw status")["output"] == "Status: inactive"
    m1.run("WAS", "ufw disable")  # 이미 꺼져 있어서 바뀐 것이 없음
    assert m1.progress()["other_actions"] == []
    m1.run("WAS", "ufw allow 8080/tcp")  # 원인과 무관한 변경 → 기록은 되지만 해결되지 않음
    assert "502" in m1.run("WEB", f"curl http://{WEB_IP}")["output"]
    assert len(m1.progress()["other_actions"]) == 1 and not m1.progress()["recovered"]


# ---------------------------------------------------------------- AI 입력 / API
def test_review_input_for_mission02_has_cause_risky_actions_and_followups(s):
    run(s, "WAS", "ufw disable")
    verify(s)
    pl = build_review_input(s)
    assert pl["real_root_cause"] == Mission02.root_cause and "방화벽" in pl["real_root_cause"]
    assert len(pl["simulator_verdict"]["risky_actions"]) == 1
    assert pl["available_followups"][0]["id"] == "mission01"
    assert "원인" in pl["available_followups"][0]["note"] and "tomcat" not in str(pl["available_followups"]).lower()


def test_review_input_for_mission01_recommends_mission02_without_spoiling():
    m1 = Session(Mission01())
    pl = build_review_input(m1)
    assert pl["available_followups"][0]["id"] == "mission02" and pl["available_followups"][0]["status"] == "available"
    assert "방화벽" not in str(pl["available_followups"])


def test_api_session_for_mission02_hides_cause():
    c = TestClient(main.app)
    sid = c.post("/api/sessions", json={"mission_id": "mission02"}).json()["sid"]
    c.post(f"/api/sessions/{sid}/command", json={"server": "WEB", "command": f"curl http://{WEB_IP}"})
    text = c.get(f"/api/sessions/{sid}").text
    assert Mission02.root_cause not in text and Mission02.correct_recovery not in text
    assert "연결되지 않는 서버" in text
