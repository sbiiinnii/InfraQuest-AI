"""진행 상황 · 복구 · 정상화 검증 판정. (AI가 아니라 규칙으로, 항상 같은 결과가 나옵니다.)"""
from __future__ import annotations

VERIFY_DIRECT = ("WAS", 8080)  # WAS 직접 요청
VERIFY_WEB = ("WEB", 80)       # WEB(Nginx) 경유 요청


def _ok_curl(f: dict, target: tuple[str, int]) -> bool:
    return (f.get("kind") == "curl" and f["dst_server"] == target[0]
            and f["port"] == target[1] and f["status"] == 200)


def evaluate(session) -> dict:
    scn, st = session.scenario, session.state
    evidence: list[str] = []
    diagnosed = False
    recovery_actions: list[str] = []
    other_actions: list[str] = []
    risky_actions: list[str] = []

    for e in session.history:
        f = e["facts"]
        ev = scn.classify(f, e["fault_active"])
        if ev:
            diagnosed = diagnosed or ev["root"]
            if ev["label"] not in evidence:
                evidence.append(ev["label"])
        if f.get("kind") in ("svc_action", "ufw_change") and f["changed"]:
            label = f"{e['server']}에서 `{e['command']}` 실행"
            (recovery_actions if scn.is_recovery(f) else other_actions).append(label)
            risky = getattr(scn, "risky_label", lambda *_: None)(f, e["command"])
            if risky:
                risky_actions.append(risky)

    healthy = not scn.fault_active(st)
    recovered = bool(recovery_actions) and healthy

    # 정상화 검증: '마지막으로 상태가 바뀐 뒤'에 WAS 직접 + WEB 경유 요청이 모두 성공해야 인정
    after = [e["facts"] for e in session.history if e["seq"] > session.last_mutation_seq]
    direct_ok = any(_ok_curl(f, VERIFY_DIRECT) for f in after)
    web_ok = any(_ok_curl(f, VERIFY_WEB) for f in after)
    verified = recovered and direct_ok and web_ok

    hypothesis = bool(session.hypotheses)
    steps = [
        {"key": "diagnose", "label": "장애 원인 분석", "done": diagnosed},
        {"key": "hypothesis", "label": "원인 가설 제출", "done": hypothesis},
        {"key": "recover", "label": "복구 조치", "done": recovered},
        {"key": "verify", "label": "정상화 검증", "done": verified},
        {"key": "review", "label": "AI 리뷰", "done": session.review_done},
    ]
    return {
        "steps": steps,
        "diagnosed": diagnosed,
        "hypothesis_submitted": hypothesis,
        "recovered": recovered,
        "verified": verified,
        "completed": verified,
        "evidence": evidence,
        "recovery_actions": recovery_actions,
        "other_actions": other_actions,
        "risky_actions": risky_actions,
        "verification": {"was_direct": direct_ok and recovered, "web": web_ok and recovered},
        "commands_total": session.counted,
        "commands_unsupported": session.unsupported,
        "hints_used": session.hints_used,
        "service_healthy": healthy,
    }
