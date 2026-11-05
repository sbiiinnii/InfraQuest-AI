"""MISSION 03 — 열렸지만 오류가 나는 웹: DB(MariaDB)가 중단되어 WAS 앱이 500 오류를 반환."""
from __future__ import annotations

from datetime import datetime

from engine.state import HOSTS, SimState, healthy_state


class Mission03:
    id = "mission03"
    title = "열렸지만 오류가 나는 웹"
    number = 3
    category = "WEB/WAS/DB 서비스 장애"
    difficulty = "초급"
    minutes = 12
    # 다음 미션 추천 화면에 보여 주는 한 줄. 원인을 알려 주지 않는 표현만 씁니다.
    training = "오류 번호를 읽고, 로그를 따라 문제가 어느 서버에 있는지 끝까지 찾아가는 연습을 해요."
    # 목록에는 원인(DB)과 오류 번호를 드러내지 않습니다.
    summary = "이번에는 지난 미션들과 다른 오류 화면이 나와요. 오류 번호가 무슨 뜻인지 읽어 보며 원인을 찾아보세요."
    situation = ("운영 중인 웹사이트에 접속하면 오류 화면이 나옵니다. 이번 오류는 지난 미션들과 모양이 달라요. "
                 "오류가 어디에서 만들어지는지 따라가 보며 원인을 찾고, 서비스를 정상화하세요.")
    goal = "장애 원인을 찾아 서비스를 정상화하고, 사용자 관점에서 정상 동작을 확인하세요."
    # 비공개 정보: 브라우저로 보내지 않고, AI 리뷰·힌트 때만 서버에서 사용합니다.
    root_cause = ("DB 서버의 MariaDB(mariadb) 서비스가 중단되어 3306 포트가 닫혀 있었고, WAS의 웹 애플리케이션이 DB에 "
                  "연결하지 못해 500 Internal Server Error가 발생했다. WEB→WAS 구간은 정상이라서 502(뒤쪽 서버에서 답을 못 받음)가 "
                  "아니라, WAS가 '답은 했지만 오류'를 돌려준 500이다. WAS의 Tomcat 서비스는 정상 실행 중이라 Tomcat을 재시작해도 "
                  "해결되지 않는다.")
    correct_recovery = ("DB 서버에서 systemctl start mariadb (또는 restart) 실행. "
                        "참고: WAS의 Tomcat이나 WEB의 Nginx를 재시작하는 것은 원인이 아니라서 해결되지 않는다.")
    # 학습자용 해설: 힌트를 모두 쓴 뒤 '해설 보기'를 눌렀을 때만 브라우저로 나갑니다.
    solution = {
        "cause": ("DB 서버의 MariaDB가 멈춰 있었어요. WAS의 웹 프로그램이 DB에 연결하지 못해 500 오류를 냈어요. "
                  "WEB → WAS 길은 멀쩡해서 502가 아니라, WAS가 '답은 했지만 안에서 오류가 났다'고 알려 준 거예요."),
        "path": ["WEB에서 `curl http://192.168.111.100` → 502가 아니라 500. 뒤쪽 서버는 답을 했다는 뜻이에요",
                 "WAS에서 `systemctl status tomcat10`, `ss -tulnp` → 둘 다 정상이에요",
                 "WAS에서 `cat /var/log/tomcat10/catalina.out` → DB(192.168.111.210:3306) 연결 실패 기록",
                 "WAS에서 `curl http://192.168.111.210:3306` → 연결 거부. 다음으로 볼 곳은 DB예요",
                 "DB에서 `systemctl status mariadb` → inactive (dead). 멈춰 있어요"],
        "fix": ["DB에서 `systemctl start mariadb`",
                "Tomcat이나 Nginx를 재시작할 필요는 없어요 (원인이 아니에요)",
                "WEB에서 `curl http://192.168.111.200:8080` 과 `curl http://192.168.111.100` 으로 둘 다 확인"],
        "lesson": "500은 '서버가 답은 했지만 안에서 오류가 났다'는 뜻이에요. 로그에서 프로그램이 어디에 연결하려다 실패했는지 따라가면 다음에 볼 서버가 보여요.",
    }
    hint_forbidden_all = [r"systemctl\s+(start|restart)", r"service\s+\S+\s+(start|restart)",
                          r"(maria\s*db|마리아\s*디비|데이터베이스|DB)\s*(서버|서비스)?\w*\s*(을|를)?\s*(다시\s*)?(재?시작|켜|살려|실행)"]
    hint_forbidden_early = [r"중단|멈춰|멈춘|꺼져|꺼진|죽어|죽은|내려가|inactive|dead|stopped"]
    followups = [
        {"id": "mission01", "title": "사라진 웹 서비스", "status": "available",
         "note": "502 오류가 나는 장애 (구체적인 원인은 알려주지 말 것)"},
        {"id": "mission02", "title": "연결되지 않는 서버", "status": "available",
         "note": "같은 502 오류인데 원인이 다른 장애 (구체적인 원인은 알려주지 말 것)"},
    ]

    def initial_state(self) -> SimState:
        st = healthy_state()
        # MariaDB를 13:39에 중단된 상태로 만들고, 그동안 쌓였을 법한 기록을 심어 둡니다.
        stop_at = datetime(2026, 11, 5, 13, 39, 48)
        st.running["mariadb"] = False
        st.changed_at["mariadb"] = datetime(2026, 11, 5, 13, 39, 51)
        desc = "MariaDB 10.11.6 database server"
        st.jlog("mariadb", f"Stopping mariadb.service - {desc}...", stop_at)
        st.jlog("mariadb", "mariadb.service: Deactivated successfully.", datetime(2026, 11, 5, 13, 39, 51))
        st.jlog("mariadb", f"Stopped mariadb.service - {desc}.", datetime(2026, 11, 5, 13, 39, 51))
        # 손님 요청이 올 때마다 WAS의 앱이 DB 연결에 실패한 기록(Tomcat 로그). Nginx에는 오류가 남지 않습니다.
        for hh, mm, ss in [(13, 42, 10), (13, 47, 31), (13, 55, 2), (14, 0, 45)]:
            st.log_app_db_error(datetime(2026, 11, 5, hh, mm, ss))
        return st

    def fault_active(self, st: SimState) -> bool:
        return not st.web_path_ok()

    def classify(self, f: dict, fault_active: bool) -> dict | None:
        """명령어 한 건이 '장애 증거'에 해당하는지 판단. root=True면 근본 원인(DB 중단)을 직접 확인한 것."""
        kind = f.get("kind")
        if kind == "svc_status" and f["service"] == "mariadb" and f["server"] == "DB" and not f["running"]:
            return {"label": "DB에서 MariaDB(mariadb) 서비스가 중단(inactive)된 것을 확인", "root": True}
        if kind == "ports" and f["server"] == "DB" and 3306 not in f["ports"]:
            return {"label": "DB에서 3306 포트가 열려 있지 않은 것을 확인", "root": True}
        if kind == "journal" and f["service"] == "mariadb" and f["server"] == "DB" and f["running"] is False:
            return {"label": "DB의 mariadb 로그에서 서비스 중지 기록을 확인", "root": True}
        if kind == "read_file" and f["file"] == "tomcat_log" and f["server"] == "WAS" and not f["empty"] and fault_active:
            return {"label": "WAS의 Tomcat 로그(catalina.out)에서 DB 연결 실패 기록을 확인", "root": False}
        if kind == "curl" and f["src"] == "WAS" and f["dst_server"] == "DB" and f["port"] == 3306 \
                and f["outcome"] in ("refused", "timeout"):
            return {"label": "WAS에서 DB(3306)로의 연결이 막히는 것을 확인", "root": False}
        if kind == "curl" and f["dst_server"] == "WEB" and f["port"] == 80 and f["status"] == 500:
            return {"label": "WEB을 통한 요청에서 500 Internal Server Error가 나는 것을 확인", "root": False}
        if kind == "curl" and f["dst_server"] == "WAS" and f["port"] == 8080 and f["status"] == 500:
            return {"label": "WAS 직접 요청에서도 500 오류가 나는 것을 확인 (Nginx가 아니라 WAS 쪽 문제)", "root": False}
        if kind == "svc_status" and f["service"] == "tomcat10" and f["server"] == "WAS" and f["running"]:
            return {"label": "WAS에서 Tomcat(tomcat10)이 정상 실행 중인 것을 확인 (서비스 중단은 원인이 아님)", "root": False}
        if kind == "ports" and f["server"] == "WAS" and 8080 in f["ports"]:
            return {"label": "WAS에서 8080 포트가 정상적으로 열려(리스닝) 있는 것을 확인", "root": False}
        return None

    def is_recovery(self, f: dict) -> bool:
        return (f.get("kind") == "svc_action" and f["service"] == "mariadb" and f["server"] == "DB"
                and f["action"] in ("start", "restart") and f["changed"] and f["running"])
