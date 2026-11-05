"""MISSION 02 — 연결되지 않는 서버: WAS 방화벽이 WEB의 8080 접속을 거부해서 같은 502가 발생."""
from __future__ import annotations

from datetime import datetime

from engine.state import HOSTS, SimState, healthy_state


class Mission02:
    id = "mission02"
    title = "연결되지 않는 서버"
    number = 2
    category = "WEB/WAS/DB 서비스 장애"
    difficulty = "초급"
    minutes = 15
    # 다음 미션 추천 화면에 보여 주는 한 줄. 원인을 알려 주지 않는 표현만 씁니다.
    training = "겉으로는 같은 오류인데 원인이 다른 장애를 구분하고, 꼭 필요한 조치만 하는 연습을 해요."
    # 목록에는 원인을 드러내지 않습니다. (미션 1을 먼저 푼 사람이 '같은 원인이겠지' 하고 넘겨짚는지 보는 미션이에요)
    summary = "502 오류가 또 발생했어요. 지난번과 같은 원인일까요? 직접 확인해 보세요."
    situation = ("운영 중인 웹사이트에서 502 Bad Gateway 오류가 다시 발생했습니다. "
                 "지난번과 같은 원인인지 직접 확인하고, 원인을 찾아 서비스를 정상화하세요.")
    goal = "장애 원인을 찾아 서비스를 정상화하고, 사용자 관점에서 정상 동작을 확인하세요."
    # 비공개 정보: 브라우저로 보내지 않고, AI 리뷰 때만 서버에서 사용합니다.
    root_cause = ("WAS 서버의 방화벽(ufw)에 WEB(192.168.111.100)에서 들어오는 8080 포트 연결을 거부(REJECT)하는 규칙이 "
                  "원래 있던 8080 허용 규칙보다 위에 있어서, Tomcat은 정상 실행 중이고 8080도 열려 있는데도 "
                  "WEB의 Nginx만 WAS에 연결하지 못해 502 Bad Gateway가 발생했다. (WAS 안이나 DB 서버에서는 접속이 된다)")
    correct_recovery = (
        "WAS 서버에서 WEB 8080 차단(REJECT) 규칙을 삭제(ufw delete)하거나, 그 규칙보다 앞에 WEB의 8080 허용 규칙을 끼워 넣기"
        "(ufw insert 1 allow from 192.168.111.100 to any port 8080 proto tcp). "
        "참고: ufw는 위에서부터 처음 맞는 규칙을 적용하므로, 차단 규칙 '뒤'에 allow만 추가하면 해결되지 않는다. "
        "방화벽을 통째로 끄는 것(ufw disable)이나 모든 출발지에 8080을 여는 것은 해결은 되지만 안전하지 않다.")
    # 학습자용 해설: 힌트를 모두 쓴 뒤 '해설 보기'를 눌렀을 때만 브라우저로 나갑니다.
    solution = {
        "cause": ("WAS의 방화벽(ufw)에 'WEB에서 오는 8080 접속을 거부'하는 규칙이 있었어요. 그 규칙이 원래 있던 "
                  "'8080 허용' 규칙보다 위에 있어서 먼저 적용됐죠. Tomcat은 멀쩡한데 WEB만 들어가지 못해서 502가 났어요."),
        "path": ["WEB에서 `curl http://192.168.111.100` → 502 확인",
                 "WAS에서 `systemctl status tomcat10`, `ss -tulnp` → 둘 다 정상. 서비스 중단이 원인이 아니에요",
                 "WAS 안에서 `curl http://localhost:8080`은 되는데 WEB에서는 안 돼요. '특정 서버만 막힌다'는 단서예요",
                 "WAS에서 `ufw status numbered` → 2번 규칙이 REJECT (또는 `cat /var/log/ufw.log`의 BLOCK 기록)"],
        "fix": ["WAS에서 `ufw delete 2` (차단 규칙 삭제. 번호는 `ufw status numbered`로 확인)",
                "또는 `ufw insert 1 allow from 192.168.111.100 to any port 8080 proto tcp` (차단 규칙보다 앞에 허용 규칙 끼우기)",
                "※ 허용 규칙을 '뒤에' 추가만 하면 안 풀려요. 방화벽은 위에서부터 처음 맞는 규칙을 적용해요",
                "※ `ufw disable`(방화벽 끄기)은 해결은 되지만 보안상 위험해요",
                "WEB에서 `curl http://192.168.111.200:8080` 과 `curl http://192.168.111.100` 으로 둘 다 확인"],
        "lesson": "같은 502라도 원인은 달라요. '서비스는 정상인데 특정 서버에서만 안 된다'면 방화벽 같은 접근 규칙을 의심해 보세요.",
    }
    hint_forbidden_all = [r"ufw\s+(delete|insert|disable|enable|allow|reject|deny|reset)",
                          r"삭제|지우|지워|제거|해제|꺼\s*보|끄(세요|면|기|고)", r"(규칙|방화벽).{0,8}(추가|끼워|풀어|열어)"]
    hint_forbidden_early = [r"REJECT|DENY|ufw|차단\s*규칙|거부\s*규칙|막는\s*규칙|막고\s*있"]
    followups = [
        {"id": "mission01", "title": "사라진 웹 서비스", "status": "available",
         "note": "같은 502 오류가 나는 또 다른 장애 (원인은 알려주지 말 것)"},
        {"id": "mission03", "title": "열렸지만 오류가 나는 웹", "status": "available",
         "note": "이번에는 다른 오류 번호가 나는 장애 (구체적인 원인은 알려주지 말 것)"},
    ]

    def initial_state(self) -> SimState:
        st = healthy_state()
        st.ufw["WAS"] = {"active": True, "rules": [
            {"port": 22, "proto": "tcp", "action": "ALLOW", "src": None},
            # 누군가 WEB 차단 규칙을 '맨 위쪽'에 끼워 넣어서, 원래 있던 8080 허용 규칙보다 먼저 적용됩니다.
            {"port": 8080, "proto": "tcp", "action": "REJECT", "src": HOSTS["WEB"]},
            {"port": 8080, "proto": "tcp", "action": "ALLOW", "src": None},
        ]}
        # 장애가 시작된 뒤 쌓였을 법한 기록: Nginx 오류 로그와 WAS의 방화벽 차단 로그가 같은 시각에 남아 있습니다.
        for hh, mm, ss, cid, client in [(13, 42, 10, 9, "203.0.113.24"), (13, 47, 31, 10, "203.0.113.57"),
                                        (13, 55, 2, 11, "198.51.100.8"), (14, 0, 45, 13, "203.0.113.24")]:
            when = datetime(2026, 11, 5, hh, mm, ss)
            st.nginx_error_log.append(
                f'2026/11/05 {hh:02}:{mm:02}:{ss:02} [error] 813#813: *{cid} connect() failed (111: Connection refused) '
                f'while connecting to upstream, client: {client}, server: _, request: "GET / HTTP/1.1", '
                f'upstream: "http://192.168.111.200:8080/", host: "192.168.111.100"')
            st.log_ufw_block("WAS", "WEB", 8080, when)
        return st

    def fault_active(self, st: SimState) -> bool:
        return not st.web_path_ok()

    def classify(self, f: dict, fault_active: bool) -> dict | None:
        """명령어 한 건이 '장애 증거'에 해당하는지 판단. root=True면 근본 원인(방화벽 차단)을 직접 확인한 것."""
        kind = f.get("kind")
        web_ip = HOSTS["WEB"]
        if kind == "ufw_status" and f["server"] == "WAS" and f["active"] and any(
                r["port"] == 8080 and r["action"] in ("REJECT", "DENY") and r["src"] in (None, web_ip)
                for r in f["rules"]):
            return {"label": "WAS의 방화벽(ufw) 규칙에서 WEB→8080 접속을 막는 규칙을 확인", "root": True}
        if kind == "read_file" and f["file"] == "ufw_log" and f["server"] == "WAS" and not f["empty"]:
            return {"label": "WAS의 방화벽 로그(ufw.log)에서 WEB의 8080 접속이 차단(BLOCK)된 기록을 확인", "root": True}
        if kind == "svc_status" and f["service"] == "tomcat10" and f["server"] == "WAS" and f["running"]:
            return {"label": "WAS에서 Tomcat(tomcat10)이 정상 실행 중인 것을 확인 (서비스 중단은 원인이 아님)", "root": False}
        if kind == "ports" and f["server"] == "WAS" and 8080 in f["ports"]:
            return {"label": "WAS에서 8080 포트가 정상적으로 열려(리스닝) 있는 것을 확인", "root": False}
        if kind == "curl" and f["src"] == "WAS" and f["dst_server"] == "WAS" and f["port"] == 8080 and f["status"] == 200:
            return {"label": "WAS 안(자기 자신)에서는 8080 요청이 정상 응답하는 것을 확인", "root": False}
        if kind == "curl" and f["src"] != "WAS" and f["dst_server"] == "WAS" and f["port"] == 8080 \
                and f["outcome"] in ("refused", "timeout"):
            return {"label": "WEB 등 다른 서버에서 WAS의 8080 요청이 막히는 것을 확인", "root": False}
        if kind == "curl" and f["dst_server"] == "WEB" and f["port"] == 80 and f["status"] in (502, 504):
            return {"label": "WEB을 통한 요청에서 502 Bad Gateway가 나는 것을 확인", "root": False}
        if kind == "read_file" and f["file"] == "nginx_error_log" and fault_active:
            return {"label": "WEB의 Nginx 오류 로그에서 WAS(업스트림) 연결 실패 기록을 확인", "root": False}
        if kind == "read_file" and f["file"] == "nginx_config" and fault_active:
            return {"label": "Nginx가 요청을 WAS(192.168.111.200:8080)로 넘기는 설정을 확인", "root": False}
        return None

    def is_recovery(self, f: dict) -> bool:
        """WEB→WAS 8080이 실제로 뚫린 방화벽 변경"""
        return (f.get("kind") == "ufw_change" and f["server"] == "WAS" and f["changed"]
                and f["unblocked_web_to_was"])

    def risky_label(self, f: dict, command: str) -> str | None:
        if f.get("kind") != "ufw_change" or not f["changed"]:
            return None
        if f["action"] == "disable":
            return f"방화벽 전체를 끄는 조치(`{command}`): 해결은 되지만 다른 포트까지 모두 열려 보안상 위험해요"
        if f["broad_allow"] and f["unblocked_web_to_was"]:
            return f"모든 출발지에 포트를 여는 조치(`{command}`): 필요한 WEB(192.168.111.100)에서만 허용하는 것이 더 안전해요"
        return None
