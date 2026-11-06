import logging
import os
import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ai.hint import MAX_HINTS, build_hint_context, generate_hint
from ai.llm import AIError
from ai.review import ReviewError, build_review_input, generate_review
from engine.recommend import recommend
from engine.session import Session
from scenarios import COMING_SOON, MISSIONS

logging.basicConfig(level=logging.WARNING, format="%(name)s: %(message)s")  # AI 검사 거절 사유가 서버 화면에 보이도록

app = FastAPI(title="InfraQuest AI")

# 배포 때 화면(Vercel)과 백엔드 주소가 달라서 필요한 허용 목록입니다.
# INFRAQUEST_ALLOWED_ORIGINS 에 화면 주소를 쉼표로 적어요. (예: https://infraquest.vercel.app) 비워 두면 다른 주소의 접근은 허용하지 않아요.
_origins = [o.strip().rstrip("/") for o in os.getenv("INFRAQUEST_ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

SESSIONS: dict[str, Session] = {}
LOCK = threading.Lock()  # 같은 세션에 요청이 동시에 들어와도 상태가 꼬이지 않게 함

# 화면에 보여 줄 서버 기본 정보. 서비스가 켜져 있는지(상태)는 일부러 넣지 않습니다.
SERVERS = [
    {"name": "WEB", "hostname": "web01", "ip": "192.168.111.100", "role": "웹 서버", "software": "Nginx", "port": 80},
    {"name": "WAS", "hostname": "was01", "ip": "192.168.111.200", "role": "애플리케이션 서버", "software": "Tomcat", "port": 8080},
    {"name": "DB", "hostname": "db01", "ip": "192.168.111.210", "role": "데이터베이스 서버", "software": "MariaDB", "port": 3306},
]


class NewSession(BaseModel):
    mission_id: str


class Command(BaseModel):
    server: str
    command: str


class Hypothesis(BaseModel):
    text: str


def get_session(sid: str) -> Session:
    s = SESSIONS.get(sid)
    if s is None:
        raise HTTPException(404, "실습 세션을 찾을 수 없어요. 새로 시작해 주세요.")
    return s


def view(sid: str, s: Session) -> dict:
    scn, p = s.scenario, s.progress()
    return {
        "sid": sid,
        "mission": {"id": scn.id, "number": scn.number, "title": scn.title, "category": scn.category,
                    "situation": scn.situation, "goal": scn.goal},  # root_cause는 보내지 않음
        "servers": SERVERS,
        "history": s.public_history(),
        "observed": s.public_observed(),  # 내가 직접 점검한 결과만 (점검 안 한 서버는 빈 목록)
        "hypotheses": [h["text"] for h in s.hypotheses],
        "review": s.review,
        "hints": [{"level": h["level"], "text": h["text"]} for h in s.hints],
        "hint_max": MAX_HINTS,
        "solution": s.public_solution(),  # 힌트를 모두 쓰고 '해설 보기'를 누르기 전에는 항상 None
        "progress": {k: p[k] for k in ("steps", "completed", "commands_total", "commands_unsupported",
                                       "evidence", "recovery_actions", "other_actions", "risky_actions", "verification",
                                       "hints_used")},
    }


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/missions")
def missions():
    ready = [{"id": m.id, "number": m.number, "title": m.title, "category": m.category,
              "difficulty": m.difficulty, "minutes": m.minutes, "summary": m.summary,
              "status": "available"}
             for m in MISSIONS.values()]
    soon = [{**m, "status": "coming_soon"} for m in COMING_SOON]
    return ready + soon


@app.post("/api/sessions")
def create_session(body: NewSession):
    scn = MISSIONS.get(body.mission_id)
    if scn is None:
        raise HTTPException(404, "아직 준비되지 않은 미션이에요.")
    sid = uuid.uuid4().hex
    with LOCK:
        SESSIONS[sid] = Session(scn)
        return view(sid, SESSIONS[sid])


@app.get("/api/sessions/{sid}")
def read_session(sid: str):
    with LOCK:
        return view(sid, get_session(sid))


@app.post("/api/sessions/{sid}/command")
def run_command(sid: str, body: Command):
    if len(body.command) > 300:
        raise HTTPException(400, "명령어가 너무 길어요. (300자 이하)")
    with LOCK:
        s = get_session(sid)
        try:
            s.run(body.server, body.command)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return view(sid, s)


@app.post("/api/sessions/{sid}/hypothesis")
def submit_hypothesis(sid: str, body: Hypothesis):
    if len(body.text) > 2000:
        raise HTTPException(400, "가설이 너무 길어요. (2000자 이하)")
    with LOCK:
        s = get_session(sid)
        try:
            s.submit_hypothesis(body.text)
        except ValueError as e:
            raise HTTPException(400, str(e))
        return view(sid, s)


@app.post("/api/sessions/{sid}/reset")
def reset_session(sid: str):
    with LOCK:
        s = get_session(sid)
        s.reset()
        return view(sid, s)


@app.post("/api/sessions/{sid}/review")
def request_review(sid: str, force: bool = False):
    """AI 선임 엔지니어 리뷰. 미션을 완료한 뒤에만 받을 수 있고, 성공한 결과만 저장합니다."""
    with LOCK:
        s = get_session(sid)
        if not s.progress()["completed"]:
            raise HTTPException(409, "미션을 완료(정상화 검증까지)한 뒤에 AI 리뷰를 받을 수 있어요.")
        if s.review is not None and not force:
            return view(sid, s)  # 이미 받은 리뷰는 다시 요청하지 않고 그대로 보여 줌
        if s.review_in_progress:
            raise HTTPException(409, "AI가 이미 리뷰를 작성하고 있어요. 잠시만 기다려 주세요.")
        s.review_in_progress = True
        payload = build_review_input(s)  # 기록을 복사해 둔 뒤, 잠금 없이 AI를 호출합니다(오래 걸릴 수 있어서)
        generation = s.seq
    try:
        review = generate_review(payload)
    except ReviewError as e:
        with LOCK:
            s.review_in_progress = False
        raise HTTPException(e.status, e.message)
    except Exception:
        with LOCK:
            s.review_in_progress = False
        raise HTTPException(500, "AI 리뷰를 만드는 중 예상하지 못한 오류가 났어요. 다시 시도해 주세요.")
    with LOCK:
        s.review_in_progress = False
        if s.seq != generation or not s.progress()["completed"]:  # 리뷰 작성 중에 초기화/추가 조작이 있었음
            raise HTTPException(409, "리뷰를 만드는 사이에 실습 상태가 바뀌었어요. 다시 요청해 주세요.")
        s.review, s.review_done = review, True
        return view(sid, s)


@app.get("/api/sessions/{sid}/recommendation")
def next_mission(sid: str, done: str = ""):
    """개인별 다음 미션 추천(규칙 기반, AI 없음). 미션을 끝낸 뒤에만 받을 수 있어요.
    done: 이미 끝낸 미션 id들을 쉼표로 이어서 보냅니다. (학습 기록은 브라우저에만 있어서 화면이 알려 줘요)"""
    with LOCK:
        s = get_session(sid)
        if not s.progress()["completed"]:
            raise HTTPException(409, "미션을 완료(정상화 검증까지)한 뒤에 다음 미션 추천을 받을 수 있어요.")
        return recommend(s, {d for d in done.split(",") if d})


@app.post("/api/sessions/{sid}/solution")
def request_solution(sid: str):
    """정답 해설: 힌트를 모두 쓴 사람만 볼 수 있어요. 끝까지 막힌 사람이 빠져나갈 길입니다. (AI를 쓰지 않음)"""
    with LOCK:
        s = get_session(sid)
        if s.progress()["completed"]:
            raise HTTPException(409, "이미 정상화를 마쳤어요. 해설은 막혔을 때만 볼 수 있어요.")
        if len(s.hints) < MAX_HINTS:
            raise HTTPException(409, f"힌트 {MAX_HINTS}개를 모두 사용한 뒤에 해설을 볼 수 있어요. (지금 {len(s.hints)}개 사용)")
        s.view_solution()
        return view(sid, s)


@app.post("/api/sessions/{sid}/hint")
def request_hint(sid: str):
    """AI 힌트: 1단계(방향) → 2단계(서버·영역) → 3단계(확인용 명령어) 순서로, 요청할 때마다 한 단계씩."""
    with LOCK:
        s = get_session(sid)
        if s.progress()["completed"]:
            raise HTTPException(409, "이미 정상화를 마쳤어요. 힌트는 실습 중에만 받을 수 있어요.")
        if len(s.hints) >= MAX_HINTS:
            raise HTTPException(409, f"힌트 {MAX_HINTS}개를 모두 사용했어요.")
        if s.hint_in_progress:
            raise HTTPException(409, "AI가 힌트를 만들고 있어요. 잠시만 기다려 주세요.")
        level = len(s.hints) + 1
        ctx = build_hint_context(s, level)  # 지금 상태를 복사해 두고, 잠금 없이 AI를 호출합니다
        epoch = s.epoch
        s.hint_in_progress = True
    try:
        text = generate_hint(ctx)
    except AIError as e:
        with LOCK:
            s.hint_in_progress = False
        raise HTTPException(e.status, e.message)
    except Exception:
        with LOCK:
            s.hint_in_progress = False
        raise HTTPException(500, "AI 힌트를 만드는 중 예상하지 못한 오류가 났어요. 다시 시도해 주세요.")
    with LOCK:
        s.hint_in_progress = False
        if s.epoch != epoch:  # 힌트를 만드는 사이에 초기화됨
            raise HTTPException(409, "힌트를 만드는 사이에 실습이 초기화됐어요. 다시 요청해 주세요.")
        s.add_hint(level, text)  # 성공한 힌트만 횟수에 포함됩니다
        return view(sid, s)
