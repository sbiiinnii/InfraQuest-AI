"""개인별 '다음 미션 추천'. (AI가 아니라 규칙으로 정합니다.)

학습자의 실제 기록(해설을 봤는지, 힌트를 몇 개 썼는지, 위험한 조치를 했는지, 원인 서버를 직접 확인했는지 등)에서
약한 부분을 찾고, 그것을 연습할 수 있는 미션을 고릅니다. 같은 기록이면 항상 같은 추천이 나오고,
AI 리뷰가 실패해도 추천은 나옵니다. 추천 글에는 다음 미션의 원인을 알려 주는 내용을 넣지 않습니다.
"""
from __future__ import annotations

from scenarios import MISSIONS

MAX_HINTS_FOR_HELP = 3   # 힌트를 이만큼 이상 썼으면 '도움을 많이 받은 것'으로 봅니다
UNSUPPORTED_LIMIT = 3    # 지원하지 않는 명령어를 이만큼 이상 시도하면 '명령어가 익숙하지 않은 것'으로 봅니다


def _mission_info(mid: str) -> dict:
    m = MISSIONS[mid]
    return {"id": m.id, "number": m.number, "title": m.title, "training": m.training,
            "difficulty": m.difficulty, "minutes": m.minutes}


def _weakness(session, p: dict) -> tuple[str, str, str, list[str], str | None] | None:
    """(코드, 연습할 것, 이유, 근거 목록, 연습에 좋은 미션 id 또는 None=지금 미션 다시) — 없으면 None"""
    if p["risky_actions"]:
        return ("risky", "필요한 조치만 안전하게 하기",
                "복구할 때 위험하거나 필요 이상으로 넓은 조치를 썼어요. 꼭 필요한 조치만 하는 연습이 필요해요.",
                list(p["risky_actions"]), "mission02")
    if session.solution_viewed or p["hints_used"] >= MAX_HINTS_FOR_HELP:
        why = ["정답 해설을 보고 풀었어요."] if session.solution_viewed else []
        why.append(f"AI 힌트를 {p['hints_used']}개 썼어요.")
        return ("helped", "도움 없이 스스로 원인 찾기",
                "이번에는 도움을 많이 받았어요. 같은 미션을 도움 없이 다시 풀면 실력이 가장 빨리 늘어요.",
                why, None)
    if not p["diagnosed"]:
        return ("no_root_check", "원인이 있는 서버를 직접 확인하기",
                "원인이 있는 서버를 직접 확인하지 않고 복구했어요. 오류 번호와 로그를 따라 원인 서버까지 가 보는 연습이 필요해요.",
                ["원인을 직접 확인한 기록이 없어요."], "mission03")
    if p["commands_unsupported"] >= UNSUPPORTED_LIMIT:
        return ("commands", "자주 쓰는 점검 명령어 익히기",
                "지원하지 않는 명령어를 여러 번 시도했어요. 기본 점검 명령어부터 익히면 진단이 빨라져요.",
                [f"지원하지 않는 명령어를 {p['commands_unsupported']}번 입력했어요."], "mission01")
    if len(p["other_actions"]) >= 2:
        return ("extra_actions", "원인에 맞는 조치만 하기",
                "원인과 직접 관련 없는 조치를 여러 번 했어요. 원인을 확인한 뒤에 필요한 조치만 하는 연습이 필요해요.",
                [f"복구와 관련 없는 조치를 {len(p['other_actions'])}번 했어요."], "mission02")
    return None


def recommend(session, done: set[str]) -> dict:
    """끝낸 세션을 보고 다음 미션을 추천합니다. `done`은 학습자가 이미 끝낸 미션 id들(브라우저가 알려 줌)."""
    p = session.progress()
    cur = session.scenario.id
    order = sorted(MISSIONS.values(), key=lambda m: m.number)
    done = {d for d in done if d in MISSIONS} | {cur}

    weak = _weakness(session, p)
    if weak:
        code, focus, reason, evidence, target = weak
        retry = target is None or target == cur
        target = cur if retry else target
        return {"kind": "weakness", "code": code, "focus": focus, "reason": reason, "evidence": evidence,
                "mission": _mission_info(target), "retry": retry,
                "already_done": (not retry) and target in done}

    # 약한 부분이 없으면: 아직 안 푼 다음 미션으로 이어 가기 (현재 번호 다음부터 돌아가며 찾음)
    n = len(order)
    start = next(i for i, m in enumerate(order) if m.id == cur)
    for i in range(1, n):
        cand = order[(start + i) % n]
        if cand.id not in done:
            return {"kind": "next", "code": "clean", "focus": "다음 단계로 나아가기",
                    "reason": "이번 미션을 도움 없이, 안전하게, 원인을 직접 확인하며 마쳤어요. 아직 풀지 않은 미션에 도전해 보세요.",
                    "evidence": ["위험한 조치 없음", "원인을 직접 확인함", f"AI 힌트 {p['hints_used']}개 사용"],
                    "mission": _mission_info(cand.id), "retry": False, "already_done": False}
    return {"kind": "all_done", "code": "all_done", "focus": "모든 미션 완료",
            "reason": "지금 있는 미션을 모두 마쳤어요. 새 미션은 준비 중이에요. 시간이 되면 도움 없이 더 빠르게 다시 풀어 보세요.",
            "evidence": ["위험한 조치 없음", "원인을 직접 확인함", f"AI 힌트 {p['hints_used']}개 사용"],
            "mission": None, "retry": False, "already_done": False}
