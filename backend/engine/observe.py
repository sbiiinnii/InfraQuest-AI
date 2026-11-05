"""서버 카드에 보여 줄 '내가 점검한 결과'.

학습자가 직접 실행한 명령어에서 **이미 화면에 나온 사실**만 모읍니다.
(점검하지 않은 서버의 상태나 원인을 미리 알려 주지 않도록, 상태표를 직접 들여다보지 않습니다.)
"""
from __future__ import annotations

from .state import SERVICES

SERVICE_PORT = {"WEB": 80, "WAS": 8080, "DB": 3306}


def observe(server: str, facts: dict) -> list[tuple[str, str, bool, str]]:
    """명령어 한 건에서 알게 된 점검 결과를 (대상 서버, 항목 이름, 정상 여부, 설명) 목록으로 돌려줍니다."""
    kind = facts.get("kind")
    if kind == "svc_status":
        svc, running = facts["service"], facts["running"]
        return [(SERVICES[svc]["server"], f"service:{svc}", running, f"{svc} 실행 중" if running else f"{svc} 중단")]
    if kind == "ports":
        port = SERVICE_PORT[facts["server"]]
        ok = port in facts["ports"]
        return [(facts["server"], "port", ok, f"{port}번 포트 열림" if ok else f"{port}번 포트 닫힘")]
    if kind == "ufw_status":
        if not facts["active"]:
            return [(facts["server"], "firewall", True, "방화벽 꺼짐")]
        blocked = any(r["action"] in ("REJECT", "DENY") for r in facts["rules"])
        return [(facts["server"], "firewall", not blocked, "차단 규칙 있음" if blocked else "차단 규칙 없음")]
    if kind == "curl" and facts.get("dst_server"):
        src, dst, port, outcome, status = (facts["src"], facts["dst_server"], facts["port"],
                                           facts["outcome"], facts["status"])
        who = "" if src == dst else f"{src}에서 "
        if outcome == "http":
            ok = status == 200
            text = f"{who}{port}번 요청 정상(200)" if ok else f"{who}{port}번 요청 오류({status})"
        elif outcome == "refused":
            ok, text = False, f"{who}{port}번 연결 거부"
        elif outcome == "timeout":
            ok, text = False, f"{who}{port}번 응답 없음"
        elif outcome == "unreachable":
            ok, text = False, f"{who}{port}번 경로 없음"
        else:  # non_http 등: 점검 결과로 보기 어려움
            return []
        return [(dst, f"curl:{src}:{port}", ok, text)]
    return []
