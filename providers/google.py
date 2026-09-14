"""Google Translate Provider.

Supports multi-tier translation resilience:
1. Official Google Cloud Translation API v2 (if API key is configured).
2. Direct Google Translate single endpoint.
3. Mobile Google Translate endpoint (failsafe against 429 rate limits).
4. MyMemory public translation fallback.
"""

import html
import re
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


class GoogleTranslateProvider(TranslationProvider):
    """Resilient Google Translate provider implementing TranslationProvider."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key.strip() if api_key else None
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

        src = "auto" if source_language in ("auto", "") else source_language
        tgt = target_language

        # Tier 1: If user configured an API key, attempt the official Google Cloud Translation API
        if self.api_key:
            try:
                return self._translate_v2_api(text, src, tgt)
            except AuthenticationError:
                raise
            except Exception as e:
                logger.warning("Google Cloud API error, attempting fallback tiers: %s", e)

        # Tier 2: Google Translate single endpoint
        try:
            return self._translate_single_endpoint(text, src, tgt)
        except (RateLimitError, TranslationError) as e:
            logger.info("Google single endpoint unavailable (%s), trying mobile endpoint...", e)

        # Tier 3: Google Translate mobile endpoint (extremely resilient against rate limits)
        try:
            return self._translate_mobile_endpoint(text, src, tgt)
        except Exception as e:
            logger.warning("Google mobile endpoint failed (%s), trying MyMemory fallback...", e)

        # Tier 4: MyMemory translation fallback
        return self._translate_mymemory(text, src, tgt)

    def _translate_v2_api(self, text: str, src: str, tgt: str) -> str:
        """Official Google Cloud Translation API v2."""
        url = "https://translation.googleapis.com/language/translate/v2"
        params = {
            "key": self.api_key,
            "q": text,
            "target": tgt,
            "format": "text",
        }
        if src != "auto":
            params["source"] = src

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, params=params)
                if response.status_code == 400:
                    data = response.json()
                    err_msg = data.get("error", {}).get("message", "Invalid request")
                    if "API key" in err_msg or "PERMISSION_DENIED" in err_msg:
                        raise AuthenticationError(f"Invalid Google API Key: {err_msg}")
                    raise TranslationError(err_msg)
                elif response.status_code == 403:
                    raise AuthenticationError("Google Translation API Key forbidden or quota exceeded")
                elif response.status_code == 429:
                    raise RateLimitError("Google Translation API rate limit reached")

                response.raise_for_status()
                data = response.json()
                translations = data.get("data", {}).get("translations", [])
                if translations:
                    return translations[0].get("translatedText", text)
                return text
        except httpx.ConnectError as e:
            raise NetworkError("Translation unavailable. Please check your internet connection.") from e
        except httpx.TimeoutException as e:
            raise NetworkError("Google Translate request timed out after 15 seconds.") from e
        except (AuthenticationError, RateLimitError):
            raise
        except Exception as e:
            raise TranslationError(f"Google Cloud Translation error: {e}") from e

    def _translate_single_endpoint(self, text: str, src: str, tgt: str) -> str:
        """Google translate single JSON endpoint."""
        url = "https://translate.googleapis.com/translate_a/single"
        params = {
            "client": "gtx",
            "sl": src,
            "tl": tgt,
            "dt": "t",
            "q": text,
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(url, params=params, headers=headers)
            if response.status_code == 429:
                raise RateLimitError("Google Translate single endpoint 429")
            response.raise_for_status()

            data = response.json()
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
                translated_segments = []
                for segment in data[0]:
                    if isinstance(segment, list) and len(segment) > 0 and segment[0]:
                        translated_segments.append(segment[0])
                if translated_segments:
                    return "".join(translated_segments)

            raise TranslationError("Unexpected response format from Google single endpoint")

    def _translate_mobile_endpoint(self, text: str, src: str, tgt: str) -> str:
        """Google translate mobile web endpoint."""
        url = "https://translate.google.com/m"
        params = {
            "sl": src,
            "tl": tgt,
            "q": text
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params, headers=headers)
                response.raise_for_status()
                match = re.search(r'class="result-container">([^<]+)<', response.text)
                if match:
                    return html.unescape(match.group(1)).strip()
                raise TranslationError("Could not extract translation from Google mobile page")
        except httpx.ConnectError as e:
            raise NetworkError("Translation unavailable. Please check your internet connection.") from e
        except httpx.TimeoutException as e:
            raise NetworkError("Google Translate request timed out after 15 seconds.") from e

    def _translate_mymemory(self, text: str, src: str, tgt: str) -> str:
        """MyMemory public translation fallback."""
        url = "https://api.mymemory.translated.net/get"
        src_clean = "vi" if src == "auto" else src
        params = {
            "q": text,
            "langpair": f"{src_clean}|{tgt}"
        }

        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                translated = data.get("responseData", {}).get("translatedText")
                if translated:
                    return html.unescape(translated).strip()
                raise TranslationError("MyMemory returned empty translation")
        except httpx.ConnectError as e:
            raise NetworkError("Translation unavailable. Please check your internet connection.") from e
        except httpx.TimeoutException as e:
            raise NetworkError("Translation request timed out after 15 seconds.") from e
        except Exception as e:
            raise TranslationError(f"All translation tiers failed: {e}") from e
