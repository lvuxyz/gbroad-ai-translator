"""Google Gemini Translation & AI Rewrite Provider."""

from typing import Optional
import httpx
from providers.http import get_client
from providers.base import (
    TranslationProvider,
    TranslationError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
)
from utils.logger import get_logger

logger = get_logger()


class GeminiProvider(TranslationProvider):
    """Translation and Rewrite provider powered by Google Gemini API."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self.api_key = api_key.strip() if api_key else None
        self.model = model or "gemini-2.5-flash"
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
                "Gemini API Key is missing. Please set your Gemini API Key in Settings."
            )

        src_desc = "Auto Detect" if source_language in ("auto", "") else source_language
        tgt_desc = target_language

        if mode == "rewrite":
            prompt = (
                f"You are a professional editor.\n\n"
                f"Rewrite and polish the following text in {style} style targeting {tgt_desc}.\n\n"
                f"Requirements:\n"
                f"- Enhance natural flow, clarity, and grammatical accuracy in {style} tone.\n"
                f"- Do not add explanations or meta commentary.\n"
                f"- Do not wrap the entire text in unnecessary quotes.\n"
                f"- Preserve line breaks, emojis, URLs, and code blocks.\n"
                f"- Preserve usernames, numbers, and special characters.\n"
                f"- Return only the rewritten text.\n\n"
                f"Text:\n{text}"
            )
        else:
            prompt = (
                f"You are a professional translator.\n\n"
                f"Translate the following text from {src_desc} to {tgt_desc}.\n\n"
                f"Requirements:\n"
                f"- Preserve the original meaning.\n"
                f"- Do not add explanations.\n"
                f"- Do not add quotation marks.\n"
                f"- Preserve line breaks.\n"
                f"- Preserve emojis.\n"
                f"- Preserve URLs.\n"
                f"- Preserve code blocks.\n"
                f"- Preserve programming syntax.\n"
                f"- Preserve usernames.\n"
                f"- Preserve numbers.\n"
                f"- Preserve special characters.\n"
                f"- Return only the translated text.\n\n"
                f"Do NOT translate source code. Only translate natural-language comments and strings when explicitly requested.\n\n"
                f"Text:\n{text}"
            )

        # The key travels in a header rather than the query string, which would
        # otherwise land in proxy and server access logs.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8,
            }
        }

        # Translation needs no deliberation, and thinking is on by default on
        # 2.5 models. Gemini 2.5 Pro cannot go below its minimum budget, so it
        # is left alone.
        if "2.5" in self.model and "pro" not in self.model.lower():
            payload["generationConfig"]["thinkingConfig"] = {"thinkingBudget": 0}

        try:
            client = get_client()
            response = client.post(url, headers=headers, json=payload, timeout=self.timeout)

            # A model that rejects thinkingConfig still deserves a translation
            if response.status_code == 400 and "thinkingConfig" in payload["generationConfig"]:
                logger.info("Model %s rejected thinkingConfig; retrying without it", self.model)
                payload["generationConfig"].pop("thinkingConfig", None)
                response = client.post(url, headers=headers, json=payload, timeout=self.timeout)

            if response.status_code == 400:
                data = response.json()
                err = data.get("error", {})
                msg = err.get("message", "Bad request")
                if "API_KEY_INVALID" in msg or "API key not valid" in msg:
                    raise AuthenticationError("Invalid Gemini API Key. Please verify your key in Settings.")
                raise TranslationError(f"Gemini API Error: {msg}")

            elif response.status_code in (401, 403):
                raise AuthenticationError("Gemini API Key authorization failed or permission denied.")

            elif response.status_code == 429:
                raise RateLimitError("Gemini rate limit exceeded. Please try again in a moment.")

            response.raise_for_status()
            data = response.json()

            # Extract text
            candidates = data.get("candidates", [])
            if not candidates:
                raise TranslationError("Gemini returned no translation candidates.")

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                raise TranslationError("Gemini returned empty response parts.")

            result_text = parts[0].get("text", "").strip()

            # If original text did not start with ``` but Gemini wrapped the whole output in ```, strip it
            if not text.strip().startswith("```") and result_text.startswith("```") and result_text.endswith("```"):
                lines = result_text.splitlines()
                if len(lines) >= 2:
                    result_text = "\n".join(lines[1:-1]).strip()

            return result_text

        except httpx.ConnectError as e:
            raise NetworkError("Translation unavailable. Please check your internet connection.") from e
        except httpx.TimeoutException as e:
            raise NetworkError("Gemini request timed out after 15 seconds.") from e
        except (AuthenticationError, RateLimitError, TranslationError):
            raise
        except Exception as e:
            raise TranslationError(f"Gemini translation failed: {e}") from e
