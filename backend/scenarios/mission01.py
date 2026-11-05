"""MISSION 01 — 사라진 웹 서비스: WAS의 Tomcat이 중단되어 Nginx가 502를 반환."""
from __future__ import annotations

from datetime import datetime

from engine.state import SimState, healthy_state


class Mission01:
    id = "mission01"
    title = "사라진 웹 서비스"
    number = 1
    category = "WEB/WAS/DB 서비스 장애"
    difficulty = "입문"
    minutes = 10
    # 다음 미션 추천 화면에 보여 주는 한 줄. 원인을 알려 주지 않는 표현만 씁니다.
    training = "장애를 '증상 → 요청이 지나가는 길 → 원인 서버' 순서로 좁혀 가는 기본기를 연습해요."
    summary = "운영 중인 웹사이트에서 502 Bad Gateway 오류가 발생했어요. 원인을 찾아 서비스를 정상화하세요."
    situation = ("운영 중인 웹사이트에 접속하면 502 Bad Gateway 오류가 발생합니다. "
                 "원인을 분석하고 서비스를 정상화하세요.")
    goal = "장애 원인을 찾아 서비스를 정상화하고, 사용자 관점에서 정상 동작을 확인하세요."
    # 비공개 정보: 클라이언트(브라우저)로 보내지 않고, AI 리뷰 때만 서버에서 사용합니다.
    root_cause = ("WAS 서버의 Tomcat(tomcat10) 서비스가 중단되어 8080 포트가 닫혀 있었고, "
                  "WEB의 Nginx가 WAS(192.168.111.200:8080)에 연결하지 못해 502 Bad Gateway가 발생했다.")
    correct_recovery = "WAS 서버에서 systemctl start tomcat10 (또는 restart) 실행"
    # 학습자용 해설: 힌트를 모두 쓴 뒤 '해설 보기'를 눌렀을 때만 브라우저로 나갑니다.
    solution = {
        "cause": ("WAS 서버의 Tomcat(웹 프로그램을 돌리는 서비스)이 멈춰 있었어요. 그래서 8080번 문이 닫혔고, "
                  "WEB의 Nginx가 WAS에 연락하지 못해 502 오류가 났어요."),
        "path": ["WEB에서 `curl http://192.168.111.100` → 502 확인 (문 앞 서버가 뒤쪽 서버에서 답을 못 받았다는 뜻이에요)",
                 "WEB에서 `curl http://192.168.111.200:8080` → 연결 거부. 문제는 WAS 쪽이에요",
                 "WAS에서 `systemctl status tomcat10` → inactive (dead). 멈춰 있어요",
                 "WAS에서 `ss -tulnp` → 8080 포트가 없어요"],
        "fix": ["WAS에서 `systemctl start tomcat10`",
                "WEB에서 `curl http://192.168.111.200:8080` 과 `curl http://192.168.111.100` 으로 둘 다 확인"],
        "lesson": "502는 '뒤쪽 서버에서 답이 없다'는 신호예요. 증상 → 요청이 지나가는 길 → 원인 서버 순서로 좁혀 가세요.",
    }
    # 힌트 검사용: 복구 방법을 직접 알려 주는 표현(모든 단계) / 원인을 직접 말하는 표현(1~2단계)
    hint_forbidden_all = [r"systemctl\s+(start|restart)", r"service\s+\S+\s+(start|restart)",
                          r"(톰캣|tomcat)\w*\s*(을|를)?\s*(다시\s*)?(재?시작|켜|살려|실행)"]
    hint_forbidden_early = [r"중단|멈춰|멈춘|꺼져|꺼진|죽어|죽은|내려가|inactive|dead|stopped"]
    followups = [
        {"id": "mission02", "title": "연결되지 않는 서버", "status": "available",
         "note": "같은 502 오류가 나지만 원인이 다른 미션 (구체적인 원인은 알려주지 말 것)"},
        {"id": "mission03", "title": "열렸지만 오류가 나는 웹", "status": "available",
         "note": "이번에는 다른 오류 번호가 나는 장애 (구체적인 원인은 알려주지 말 것)"},
    ]

    def initial_state(self) -> SimState:
        st = healthy_state()
        # Tomcat을 13:41에 중단된 상태로 만들고, 그동안 쌓였을 법한 기록을 심어 둡니다.
        stop_at = datetime(2026, 11, 5, 13, 41, 52)
        st.running["tomcat10"] = False
        st.changed_at["tomcat10"] = datetime(2026, 11, 5, 13, 41, 55)
        desc = "Apache Tomcat 10 Web Application Server"
        st.jlog("tomcat10", f"Stopping tomcat10.service - {desc}...", stop_at)
        st.jlog("tomcat10", "tomcat10.service: Deactivated successfully.", datetime(2026, 11, 5, 13, 41, 55))
        st.jlog("tomcat10", f"Stopped tomcat10.service - {desc}.", datetime(2026, 11, 5, 13, 41, 55))
        for sec, cid, client in [("13:42:10", 9, "203.0.113.24"), ("13:47:31", 10, "203.0.113.57"),
                                 ("13:55:02", 11, "198.51.100.8"), ("14:00:45", 13, "203.0.113.24")]:
            st.nginx_error_log.append(
                f'2026/11/05 {sec} [error] 813#813: *{cid} connect() failed (111: Connection refused) while '
                f'connecting to upstream, client: {client}, server: _, request: "GET / HTTP/1.1", '
                f'upstream: "http://192.168.111.200:8080/", host: "192.168.111.100"')
        return st

    def fault_active(self, st: SimState) -> bool:
        return not st.running["tomcat10"]

    def classify(self, f: dict, fault_active: bool) -> dict | None:
        """명령어 한 건이 '장애 증거'에 해당하는지 판단. root=True면 근본 원인을 직접 확인한 것."""
        kind = f.get("kind")
        if kind == "svc_status" and f["service"] == "tomcat10" and f["server"] == "WAS" and not f["running"]:
            return {"label": "WAS에서 Tomcat(tomcat10) 서비스가 중단(inactive)된 것을 확인", "root": True}
        if kind == "ports" and f["server"] == "WAS" and 8080 not in f["ports"]:
            return {"label": "WAS에서 8080 포트가 열려 있지 않은 것을 확인", "root": True}
        if kind == "journal" and f["service"] == "tomcat10" and f["server"] == "WAS" and f["running"] is False:
            return {"label": "WAS의 tomcat10 로그에서 서비스 중지 기록을 확인", "root": True}
        if kind == "curl" and f["dst_server"] == "WEB" and f["port"] == 80 and f["status"] == 502:
            return {"label": "WEB을 통한 요청에서 502 Bad Gateway가 나는 것을 확인", "root": False}
        if kind == "curl" and f["dst_server"] == "WAS" and f["port"] == 8080 and f["outcome"] == "refused":
            return {"label": "WAS의 8080 포트 직접 요청이 연결 거부되는 것을 확인", "root": False}
        if kind == "read_file" and f["file"] == "nginx_error_log" and fault_active:
            return {"label": "WEB의 Nginx 오류 로그에서 WAS(업스트림) 연결 실패 기록을 확인", "root": False}
        if kind == "read_file" and f["file"] == "nginx_config" and fault_active:
            return {"label": "Nginx가 요청을 WAS(192.168.111.200:8080)로 넘기는 설정을 확인", "root": False}
        return None

    def is_recovery(self, f: dict) -> bool:
        return (f.get("kind") == "svc_action" and f["service"] == "tomcat10" and f["server"] == "WAS"
                and f["action"] in ("start", "restart") and f["changed"] and f["running"])
