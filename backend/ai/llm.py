"""AI 호출 공통 부분 (AI 리뷰와 AI 힌트가 함께 씁니다). Claude(Anthropic)를 기본으로 쓰고, OpenAI 키만 있으면 OpenAI로 불러요."""
from __future__ import annotations

import logging
import os

import anthropic
import openai
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger("infraquest.llm")

MODEL = os.getenv("INFRAQUEST_MODEL", "claude-opus-5-5")
OPENAI_MODEL = os.getenv("INFRAQUEST_OPENAI_MODEL", "gpt-5-mini")
FALLBACK_MODELS = {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}


class AIError(Exception):
    """사용자에게 그대로 보여줄 수 있는 AI 관련 오류"""

    def __init__(self, message: str, status: int = 502):
        super().__init__(message)
        self.message, self.status = message, status


def _clean_key() -> str:
    """OPENAI_API_KEY 또는 ANTHROPIC_API_KEY 에 든 키를 가져와요. 호스팅 화면에 붙여넣다 생긴 앞뒤 공백·따옴표는 지워요."""
    raw = os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or ""
    return raw.strip().strip("\"'")


def provider() -> str:
    """키 모양으로 어느 회사 AI를 쓸지 정해요. 'sk-ant-'로 시작하면 Claude, 그 외 'sk-' 키는 OpenAI."""
    key = _clean_key()
    return "anthropic" if (not key or key.startswith("sk-ant-")) else "openai"


def make_client():
    key = _clean_key()
    if not key:
        raise AIError("AI 기능을 쓰려면 API 키 설정이 필요해요. backend 폴더의 .env 파일에 ANTHROPIC_API_KEY(또는 OPENAI_API_KEY)를 넣고 "
                      "백엔드를 다시 실행해 주세요.", 503)
    if provider() == "openai":
        return openai.OpenAI(api_key=key, timeout=120.0, max_retries=2)
    os.environ["ANTHROPIC_API_KEY"] = key
    return anthropic.Anthropic(timeout=120.0, max_retries=2)


def _call_openai(client, *, system: str, user_text: str, schema: dict, max_tokens: int) -> str:
    """OpenAI로 JSON 답을 받아요. 답의 모양은 프롬프트에 스키마를 넣어 맞추고, 이후 검사는 기존 코드가 해요."""
    import json

    sys_prompt = (system + "\n\n반드시 아래 JSON 스키마에 맞는 JSON 객체 하나만 출력하세요. 설명 문장이나 코드블록 없이 JSON만 출력합니다.\n"
                  + json.dumps(schema, ensure_ascii=False))
    try:
        extra = {"reasoning_effort": "low"} if OPENAI_MODEL.startswith(("gpt-5", "o1", "o3", "o4")) else {}  # 생각하는 모델은 빠르게
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            max_completion_tokens=min(max_tokens, 12000),
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": sys_prompt}, {"role": "user", "content": user_text}],
            **extra,
        )
    except openai.AuthenticationError:
        raise AIError("API 키가 올바르지 않아요. 서버에 넣은 OPENAI_API_KEY(또는 ANTHROPIC_API_KEY)를 확인해 주세요.", 502)
    except openai.PermissionDeniedError:
        raise AIError("이 API 키로는 AI 기능을 쓸 수 없어요. 키의 권한을 확인해 주세요.", 502)
    except openai.RateLimitError:
        raise AIError("지금 AI 요청이 몰려 있거나 사용 한도를 넘었어요. 잠시 뒤에 다시 시도해 주세요.", 429)
    except (openai.APIConnectionError, openai.APITimeoutError):
        raise AIError("AI 서버에 연결하지 못했어요. 인터넷 연결을 확인하고 다시 시도해 주세요.", 503)
    except openai.APIStatusError as e:
        log.error("OpenAI API 오류 %s: %s", e.status_code, e.message)
        raise AIError(f"AI 서버에서 오류가 났어요. 잠시 뒤에 다시 시도해 주세요. (코드 {e.status_code})", 502)
    choice = resp.choices[0]
    if choice.finish_reason == "length":
        raise AIError("AI 답변이 중간에 끊겼어요. 다시 시도해 주세요.", 502)
    text = choice.message.content or ""
    if not text:
        raise AIError("AI가 빈 답변을 보냈어요. 다시 시도해 주세요.", 502)
    return text


def call_json(client, *, system: str, user_text: str, schema: dict,
              effort: str = "medium", max_tokens: int = 16000) -> str:
    """JSON 스키마로 답을 받아 '글자(JSON 문자열)'로 돌려줍니다. 실패하면 AIError를 일으킵니다."""
    if isinstance(client, openai.OpenAI):
        return _call_openai(client, system=system, user_text=user_text, schema=schema, max_tokens=max_tokens)
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
