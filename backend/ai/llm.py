"""Claude API 호출 공통 부분 (AI 리뷰와 AI 힌트가 함께 씁니다)."""
from __future__ import annotations

import logging
import os

import anthropic
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("infraquest.llm")

MODEL = os.getenv("INFRAQUEST_MODEL", "claude-opus-5-5")
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


class AIError(Exception):
    """사용자에게 그대로 보여줄 수 있는 AI 관련 오류"""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message, self.status = message, status


def make_client() -> anthropic.Anthropic:
    # 호스팅 설정 화면에 키를 넣을 때 끝에 줄바꿈·공백이 같이 들어가는 경우가 있어서 지워 줘요.
    key = os.getenv("ANTHROPIC_API_KEY", "").strip().strip("\"'")
    if key:
        os.environ["ANTHROPIC_API_KEY"] = key
    if not os.getenv("ANTHROPIC_API_KEY"):
        raise AIError("AI 기능을 쓰려면 API 키 설정이 필요해요. backend 폴더의 .env 파일에 ANTHROPIC_API_KEY를 넣고 "
                      "백엔드를 다시 실행해 주세요.", 503)
    return anthropic.Anthropic(timeout=120.0, max_retries=2)


def call_json(client: anthropic.Anthropic, *, system: str, user_text: str, schema: dict,
              effort: str = "medium", max_tokens: int = 16000) -> str:
    """JSON 스키마로 답을 받아 '글자(JSON 문자열)'로 돌려줍니다. 실패하면 AIError를 일으킵니다."""
    kwargs = dict(
        model=MODEL,
        max_tokens=max_tokens,
        system=system,
        output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
        messages=[{"role": "user", "content": user_text}],
    )
    try:
        if MODEL in FALLBACK_MODELS:  # 안전 분류기가 요청을 거절하면 서버가 대체 모델로 자동 재시도
            resp = client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kwargs)
        else:
            resp = client.messages.create(**kwargs)
    except anthropic.AuthenticationError:
        raise AIError("API 키가 올바르지 않아요. backend/.env의 ANTHROPIC_API_KEY를 확인해 주세요.", 502)
    except anthropic.PermissionDeniedError:
        raise AIError("이 API 키로는 AI 기능을 쓸 수 없어요. 키의 권한을 확인해 주세요.", 502)
    except anthropic.RateLimitError:
        raise AIError("지금 AI 요청이 몰려 있어요. 잠시 뒤에 다시 시도해 주세요.", 429)
    except (anthropic.APIConnectionError, anthropic.APITimeoutError):
        raise AIError("AI 서버에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요.", 503)
    except anthropic.APIStatusError as e:
        log.error("Claude API 오류 %s: %s", e.status_code, e.message)
        raise AIError(f"AI 서버에서 오류가 났어요. 잠시 뒤에 다시 시도해 주세요. (코드 {e.status_code})", 502)

    if resp.stop_reason == "refusal":
        raise AIError("AI가 이번 요청에 답하지 못했어요. 다시 시도해 주세요.", 502)
    if resp.stop_reason == "max_tokens":
        raise AIError("AI 답변이 중간에 끊겼어요. 다시 시도해 주세요.", 502)
    text = next((b.text for b in resp.content if b.type == "text"), "")
    if not text:
        raise AIError("AI가 빈 답변을 보냈어요. 다시 시도해 주세요.", 502)
    return text
