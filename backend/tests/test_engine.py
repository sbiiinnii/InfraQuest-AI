import pytest

from engine.session import Session
from engine.state import HOSTS, SimState
from scenarios.mission01 import Mission01


@pytest.fixture
def s():
    return Session(Mission01())


def run(s, server, cmd):
    return s.run(server, cmd)


# ---------------------------------------------------------------- 초기 상태(장애)
def test_initial_symptom_is_502_via_web(s):
    e = run(s, "WEB", "curl http://192.168.111.100")
    assert "502 Bad Gateway" in e["output"] and e["exit_code"] == 0


def test_initial_web_to_was_connection_refused(s):
    e = run(s, "WEB", "curl http://192.168.111.200:8080")
    assert e["exit_code"] == 7 and "Couldn't connect to server" in e["output"]


def test_initial_was_status_inactive_and_port_closed(s):
    st = run(s, "WAS", "systemctl status tomcat10")
    assert "inactive (dead)" in st["output"] and st["exit_code"] == 3
    ports = run(s, "WAS", "ss -tulnp")["output"]
    assert ":8080" not in ports and ":22" in ports


def test_other_services_running_initially(s):
    assert "active (running)" in run(s, "WEB", "systemctl status nginx")["output"]
    assert "active (running)" in run(s, "DB", "systemctl status mariadb")["output"]
    assert ":80 " in run(s, "WEB", "ss -tulnp")["output"] + " "
    assert ":3306" in run(s, "DB", "ss -tulnp")["output"]


def test_nginx_error_log_shows_upstream_failure(s):
    out = run(s, "WEB", "tail -n 3 /var/log/nginx/error.log")["output"]
    assert out.count("Connection refused") == 3 and "192.168.111.200:8080" in out


def test_nginx_config_points_to_was(s):
    assert "proxy_pass http://192.168.111.200:8080" in run(s, "WEB", "cat /etc/nginx/sites-enabled/default")["output"]


def test_failed_web_request_appends_error_log(s):
    before = run(s, "WEB", "cat /var/log/nginx/error.log")["output"].count("\n")
    run(s, "DB", "curl http://192.168.111.100")
    after = run(s, "WEB", "cat /var/log/nginx/error.log")["output"]
    assert after.count("\n") == before + 1 and "client: 192.168.111.210" in after


# ---------------------------------------------------------------- 복구 후 일관성
def test_start_tomcat_changes_everything_consistently(s):
    assert run(s, "WAS", "systemctl start tomcat10")["output"] == ""
    assert "active (running)" in run(s, "WAS", "systemctl status tomcat10")["output"]
    assert ":8080" in run(s, "WAS", "ss -tulnp")["output"]
    assert "InfraQuest Shop" in run(s, "WEB", "curl http://192.168.111.200:8080")["output"]
    assert "InfraQuest Shop" in run(s, "WEB", "curl http://192.168.111.100")["output"]
    assert "Started tomcat10.service" in run(s, "WAS", "journalctl -u tomcat10 -n 2")["output"]
    assert run(s, "WAS", "systemctl is-active tomcat10")["output"] == "active"


def test_stop_again_breaks_service_again(s):
    run(s, "WAS", "systemctl start tomcat10")
    run(s, "WAS", "systemctl stop tomcat10")
    assert "502" in run(s, "WEB", "curl 192.168.111.100")["output"]


def test_stopping_nginx_gives_connection_refused_on_80(s):
    run(s, "WAS", "systemctl start tomcat10")
    run(s, "WEB", "systemctl stop nginx")
    e = run(s, "WAS", "curl http://192.168.111.100")
    assert e["exit_code"] == 7
    assert ":80 " not in run(s, "WEB", "ss -tulnp")["output"] + " "


def test_restart_gives_new_pid(s):
    run(s, "WAS", "systemctl start tomcat10")
    pid1 = run(s, "WAS", "ss -tulnp")["output"].split("java")[1][:12]
    run(s, "WAS", "systemctl restart tomcat10")
    pid2 = run(s, "WAS", "ss -tulnp")["output"].split("java")[1][:12]
    assert pid1 != pid2


# ---------------------------------------------------------------- 잘못된 서버 / 지원하지 않는 명령
def test_wrong_server_unit_not_found(s):
    e = run(s, "WEB", "systemctl status tomcat10")
    assert "could not be found" in e["output"] and e["exit_code"] == 4
    assert "could not be found" in run(s, "WAS", "systemctl status nginx")["output"]
    e = run(s, "WEB", "systemctl start tomcat10")
    assert "not found" in e["output"] and e["exit_code"] == 5
    # 잘못된 서버에서 실행해도 WAS 상태는 변하지 않음
    assert "inactive" in run(s, "WAS", "systemctl status tomcat10")["output"]


def test_wrong_server_file(s):
    assert "No such file" in run(s, "WAS", "cat /etc/nginx/sites-enabled/default")["output"]


@pytest.mark.parametrize("cmd", ["ls", "rm -rf /", "reboot", "ping 192.168.111.200",
                                 "curl http://192.168.111.100 | head", "systemctl start tomcat10 && ls",
                                 "systemctl enable tomcat10", "cat /etc/passwd", "curl -v 192.168.111.100"])
def test_unsupported_commands_are_honest_and_change_nothing(s, cmd):
    e = run(s, "WAS", cmd)
    assert e["supported"] is False and e["output"].startswith("[가상 터미널]")
    assert "inactive" in run(s, "WAS", "systemctl status tomcat10")["output"]
    assert s.unsupported == 1


def test_whitespace_sudo_and_service_alias(s):
    run(s, "WAS", "   sudo   systemctl    start   tomcat10.service  ")
    assert "active (running)" in run(s, "WAS", "service tomcat10 status")["output"]


def test_empty_input_is_ignored(s):
    assert run(s, "WAS", "   ") is None and s.counted == 0


def test_invalid_server_rejected(s):
    with pytest.raises(ValueError):
        run(s, "HACKER", "ls")


def test_curl_silent_hides_error_unless_S(s):
    assert run(s, "WEB", "curl -s http://192.168.111.200:8080")["output"] == ""
    assert "curl: (7)" in run(s, "WEB", "curl -sS http://192.168.111.200:8080")["output"]


def test_curl_head_and_localhost(s):
    run(s, "WAS", "systemctl start tomcat10")
    assert run(s, "WAS", "curl -I http://localhost:8080")["output"].startswith("HTTP/1.1 200")
    assert "502" not in run(s, "WEB", "curl -I localhost")["output"]
    assert run(s, "WEB", "curl http://nowhere.example")["exit_code"] == 6


def test_help_and_clear_not_counted(s):
    run(s, "WEB", "help")
    run(s, "WEB", "clear")
    assert s.counted == 0
    run(s, "WEB", "hostname")
    assert s.counted == 1


# ---------------------------------------------------------------- 진행 상태 · 완료 판정
def steps(s):
    return {x["key"]: x["done"] for x in s.progress()["steps"]}


def test_nothing_done_at_start(s):
    assert not any(steps(s).values())


def test_diagnose_only_marked_after_real_evidence(s):
    run(s, "WEB", "curl http://192.168.111.100")  # 증상 확인일 뿐, 근본 원인 확인은 아님
    assert steps(s)["diagnose"] is False
    assert s.progress()["evidence"]
    run(s, "WAS", "systemctl status tomcat10")
    assert steps(s)["diagnose"] is True


def test_diagnose_not_marked_when_checking_wrong_server(s):
    run(s, "WEB", "systemctl status tomcat10")
    run(s, "DB", "ss -tulnp")
    assert steps(s)["diagnose"] is False


def test_recovery_alone_does_not_complete(s):
    run(s, "WAS", "systemctl start tomcat10")
    p = s.progress()
    assert p["recovered"] is True and p["verified"] is False and p["completed"] is False


def test_direct_check_only_does_not_complete(s):
    run(s, "WAS", "systemctl start tomcat10")
    run(s, "WEB", "curl http://192.168.111.200:8080")
    assert s.progress()["completed"] is False


def test_full_flow_completes(s):
    run(s, "WEB", "curl http://192.168.111.100")
    run(s, "WAS", "systemctl status tomcat10")
    s.submit_hypothesis("Tomcat이 중단되어 8080이 닫혀 있어 502 발생")
    run(s, "WAS", "systemctl start tomcat10")
    run(s, "WEB", "curl http://192.168.111.200:8080")
    run(s, "WEB", "curl http://192.168.111.100")
    p = s.progress()
    assert p["completed"] and p["verification"] == {"was_direct": True, "web": True}
    assert all(x["done"] for x in p["steps"] if x["key"] != "review")
    assert p["recovery_actions"] == ["WAS에서 `systemctl start tomcat10` 실행"]
    assert p["commands_total"] == 5  # 가설 제출은 명령어로 세지 않음


def test_verification_before_recovery_does_not_count(s):
    run(s, "WEB", "curl http://192.168.111.200:8080")
    run(s, "WEB", "curl http://192.168.111.100")
    run(s, "WAS", "systemctl start tomcat10")
    assert s.progress()["completed"] is False


def test_mutation_after_verification_requires_reverification(s):
    run(s, "WAS", "systemctl start tomcat10")
    run(s, "WEB", "curl 192.168.111.200:8080")
    run(s, "WEB", "curl 192.168.111.100")
    assert s.progress()["completed"]
    run(s, "WEB", "systemctl restart nginx")
    p = s.progress()
    assert p["completed"] is False and p["other_actions"] == ["WEB에서 `systemctl restart nginx` 실행"]
    run(s, "WEB", "curl 192.168.111.100")
    assert s.progress()["completed"] is False  # WAS 직접 확인도 다시 필요
    run(s, "WEB", "curl 192.168.111.200:8080")
    assert s.progress()["completed"]


def test_breaking_service_after_recovery_uncompletes(s):
    run(s, "WAS", "systemctl start tomcat10")
    run(s, "WEB", "curl 192.168.111.200:8080")
    run(s, "WEB", "curl 192.168.111.100")
    run(s, "WAS", "systemctl stop tomcat10")
    p = s.progress()
    assert not p["recovered"] and not p["completed"]


def test_completion_without_diagnosis_or_hypothesis_is_reported_honestly(s):
    run(s, "WAS", "systemctl start tomcat10")
    run(s, "WEB", "curl 192.168.111.200:8080")
    run(s, "WEB", "curl 192.168.111.100")
    p = s.progress()
    assert p["completed"] and not p["diagnosed"] and not p["hypothesis_submitted"]


def test_hypothesis_records_timing_and_rejects_empty(s):
    run(s, "WAS", "ss -tulnp")
    s.submit_hypothesis("  WAS 8080 닫힘  ")
    assert s.hypotheses == [{"text": "WAS 8080 닫힘", "after_seq": 1}]
    with pytest.raises(ValueError):
        s.submit_hypothesis("   ")


def test_reset_restores_fault_and_clears_everything(s):
    run(s, "WAS", "systemctl start tomcat10")
    s.submit_hypothesis("x")
    s.reset()
    assert "502" in run(s, "WEB", "curl 192.168.111.100")["output"]
    assert s.seq == 1 and s.hypotheses == [] and s.last_mutation_seq == 0


def test_public_history_hides_internal_facts(s):
    run(s, "WAS", "systemctl status tomcat10")
    h = s.public_history()[0]
    assert "facts" not in h and "fault_active" not in h


def test_root_cause_never_in_public_history_or_initial_ui_data(s):
    run(s, "WEB", "curl 192.168.111.100")
    assert Mission01.root_cause not in str(s.public_history())


# ---------------------------------------------------------------- 방화벽 모델(미션 2 대비)
def fw_state(action):
    st = SimState()
    st.ufw["WAS"] = {"active": True, "rules": [
        {"port": 22, "proto": "tcp", "action": "ALLOW", "src": None},
        {"port": 8080, "proto": "tcp", "action": action, "src": HOSTS["WEB"]},
    ]}
    return st


def test_firewall_reject_gives_refused_and_502():
    st = fw_state("REJECT")
    assert st.tcp_connect("WEB", HOSTS["WAS"], 8080) == "refused"
    assert st.http_request("DB", HOSTS["WEB"], 80, "x", "c")["status"] == 502
    # 규칙에 없는 출발지(DB)는 ufw 기본 정책(차단, 응답 없음)이 적용됨
    assert st.tcp_connect("DB", HOSTS["WAS"], 8080) == "timeout"


def test_firewall_deny_gives_timeout_and_504():
    st = fw_state("DENY")
    assert st.tcp_connect("WEB", HOSTS["WAS"], 8080) == "timeout"
    assert st.http_request("DB", HOSTS["WEB"], 80, "x", "c")["status"] == 504


def test_firewall_allow_passes_and_loopback_bypasses():
    st = fw_state("ALLOW")
    assert st.tcp_connect("WEB", HOSTS["WAS"], 8080) == "ok"
    st.ufw["WAS"]["rules"] = [{"port": 22, "proto": "tcp", "action": "ALLOW", "src": None}]
    assert st.tcp_connect("WEB", HOSTS["WAS"], 8080) == "timeout"  # 허용 규칙이 없어 기본 차단
    assert st.tcp_connect("WAS", HOSTS["WAS"], 8080) == "ok"  # 자기 자신(루프백)은 방화벽 무시


def test_ufw_status_output_matches_rules():
    sess = Session(Mission01())
    sess.state = fw_state("REJECT")
    out = sess.run("WAS", "ufw status")["output"]
    assert "Status: active" in out and "8080/tcp" in out and "REJECT" in out and "192.168.111.100" in out
    assert sess.run("WEB", "ufw status")["output"] == "Status: inactive"
