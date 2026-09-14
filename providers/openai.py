"""OpenAI Translation & AI Rewrite Provider."""

from typing import Optional
import httpx
from providers.base import (
    TranslationProvider,
    TranslationError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
)
from utils.logger import get_logger

logger = get_logger()


class OpenAIProvider(TranslationProvider):
    """Translation and Rewrite provider powered by OpenAI Chat Completions API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key.strip() if api_key else None
        self.model = model or "gpt-4o-mini"
        self.timeout = 15.0

    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        mode: str = "translate",
        style: str = "natural"
    ) -> str:
        if not text or not text.strip():
            return text

        if not self.api_key:
            raise AuthenticationError(
                "OpenAI API Key is missing. Please set your OpenAI API Key in Settings."
            )

        src_desc = "Auto Detect" if source_language in ("auto", "") else source_language
        tgt_desc = target_language

        if mode == "rewrite":
            system_prompt = (
                f"You are a professional editor. Rewrite and polish text in {style} style targeting {tgt_desc}.\n"
                f"Requirements:\n"
                f"- Enhance clarity, flow, and grammatical correctness in {style} tone.\n"
                f"- Do not add explanations or commentary.\n"
                f"- Do not wrap the output in quotes.\n"
                f"- Preserve emojis, URLs, code blocks, line breaks, usernames, numbers.\n"
                f"- Return only the rewritten text."
            )
        else:
            system_prompt = (
                f"You are a professional translator.\n"
                f"Translate the text from {src_desc} to {tgt_desc}.\n\n"
                f"Requirements:\n"
                f"- Preserve original meaning.\n"
                f"- Do not add explanations or quotation marks.\n"
                f"- Preserve line breaks, emojis, URLs, numbers, special characters, and usernames.\n"
                f"- Preserve code blocks and programming syntax. Do NOT translate source code.\n"
                f"- Return only the translated text."
            )

        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ]
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=payload)

                if response.status_code == 401:
                    raise AuthenticationError("Invalid OpenAI API Key. Please check your key in Settings.")
                elif response.status_code == 429:
                    raise RateLimitError("OpenAI rate limit or quota exceeded. Please check your billing.")
                elif response.status_code == 400:
                    data = response.json()
                    err = data.get("error", {}).get("message", "Bad request")
                    raise TranslationError(f"OpenAI Error: {err}")

                response.raise_for_status()
                data = response.json()

                choices = data.get("choices", [])
                if not choices:
                    raise TranslationError("OpenAI returned no choices.")

                result_text = choices[0].get("message", {}).get("content", "").strip()

                # Clean accidental outer triple backtick wrapping
                if not text.strip().startswith("```") and result_text.startswith("```") and result_text.endswith("```"):
                    lines = result_text.splitlines()
                    if len(lines) >= 2:
                        result_text = "\n".join(lines[1:-1]).strip()

                return result_text

        except httpx.ConnectError as e:
            raise NetworkError("Translation unavailable. Please check your internet connection.") from e
        except httpx.TimeoutException as e:
            raise NetworkError("OpenAI request timed out after 15 seconds.") from e
        except (AuthenticationError, RateLimitError, TranslationError):
            raise
        except Exception as e:
            raise TranslationError(f"OpenAI translation failed: {e}") from e
