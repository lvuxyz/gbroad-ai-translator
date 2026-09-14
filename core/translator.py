"""Translation orchestrator.

Coordinates provider instantiation, retry with exponential backoff,
timeout enforcement, text post-processing, and history recording.
"""

import time
import threading
from collections import OrderedDict
from typing import Optional, Dict, Any, Tuple
from providers.base import (
    TranslationProvider,
    TranslationError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
)
from providers.google import GoogleTranslateProvider
from providers.gemini import GeminiProvider
from providers.openai import OpenAIProvider
from core.text_processor import TextProcessor
from config import get_config
from database import get_database
from utils.logger import get_logger

logger = get_logger()


class TranslationCache:
    """Bounded, in-memory cache of recent translation results.

    Repeating a translation is ordinary use: retrying after a mistyped
    selection, or sending the same greeting to a second person. Each repeat
    otherwise costs a full network round trip.

    Entries live in memory only and never reach disk, and the cache is bypassed
    entirely while Privacy Mode is on.
    """

    def __init__(self, max_entries: int = 128, ttl_seconds: float = 600.0):
        self._entries: "OrderedDict[Tuple, Tuple[float, str]]" = OrderedDict()
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def get(self, key: Tuple) -> Optional[str]:
        """Returns the cached result, or None if absent or expired."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if time.monotonic() - stored_at > self._ttl:
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    def put(self, key: Tuple, value: str) -> None:
        """Stores a result, evicting the least recently used entry when full."""
        with self._lock:
            self._entries[key] = (time.monotonic(), value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        """Drops every cached result."""
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)


class TranslatorService:
    """Orchestrates translation operations, retries, and history logging."""

    def __init__(self):
        self.config = get_config()
        self.db = get_database()
        self.text_processor = TextProcessor()
        self.cache = TranslationCache()

    def get_provider(self, provider_name: Optional[str] = None) -> TranslationProvider:
        """Instantiates the requested or currently configured translation provider."""
        name = (provider_name or self.config.get("provider", "google")).lower()
        api_key = self.config.get_api_key(name)

        if name == "gemini":
            if not api_key:
                logger.warning("Gemini API key is not configured; falling back to Google Translate")
                return GoogleTranslateProvider(api_key=self.config.get_api_key("google"))
            model = self.config.get("gemini_model", "gemini-2.5-flash")
            return GeminiProvider(api_key=api_key, model=model)
        elif name == "openai":
            if not api_key:
                logger.warning("OpenAI API key is not configured; falling back to Google Translate")
                return GoogleTranslateProvider(api_key=self.config.get_api_key("google"))
            model = self.config.get("openai_model", "gpt-4o-mini")
            return OpenAIProvider(api_key=api_key, model=model)
        elif name == "google":
            return GoogleTranslateProvider(api_key=api_key)
        else:
            logger.warning("Unknown provider '%s', defaulting to Google Translate", name)
            return GoogleTranslateProvider(api_key=api_key)

    def translate_text(
        self,
        text: str,
        target_language: Optional[str] = None,
        source_language: Optional[str] = None,
        provider_name: Optional[str] = None,
        mode: Optional[str] = None,
        style: Optional[str] = None
    ) -> str:
        """Translates or rewrites text with retry and exponential backoff.

        Args:
            text: Text to translate.
            target_language: Target language code (e.g. 'en', 'ja').
            source_language: Source language code (e.g. 'auto', 'vi').
            provider_name: Provider name ('gemini', 'openai', 'google').
            mode: 'translate' or 'rewrite'.
            style: 'natural', 'formal', 'casual', 'polish'.

        Returns:
            The translated or rewritten text with spacing preserved.

        Raises:
            TranslationError, AuthenticationError, NetworkError, RateLimitError
        """
        if not text or not text.strip():
            return text

        # Extract leading and trailing whitespace to preserve original formatting
        leading, body, trailing = self.text_processor.extract_spacing(text)
        if not body:
            return text

        src_lang = source_language or self.config.get("source_language", "auto")
        tgt_lang = target_language or self.config.get("target_language", "en")
        trans_mode = mode or self.config.get("mode", "translate")
        rewrite_style = style or self.config.get("rewrite_style", "natural")
        active_provider_name = (provider_name or self.config.get("provider", "gemini")).lower()

        # Privacy Mode keeps nothing about the text around, cache included
        privacy_mode = self.config.get("privacy_mode", False)
        cache_key = (body, src_lang, tgt_lang, active_provider_name, trans_mode, rewrite_style)

        if not privacy_mode:
            cached = self.cache.get(cache_key)
            if cached is not None:
                logger.info("Serving translation from cache (text_length=%d)", len(body))
                return self.text_processor.apply_spacing(cached, leading, trailing)

        provider = self.get_provider(active_provider_name)

        max_retries = 2
        last_error: Optional[Exception] = None

        logger.info(
            "Starting translation: src=%s, tgt=%s, provider=%s, mode=%s, text_length=%d",
            src_lang, tgt_lang, active_provider_name, trans_mode, len(body)
        )

        for attempt in range(max_retries + 1):
            try:
                raw_result = provider.translate(
                    text=body,
                    source_language=src_lang,
                    target_language=tgt_lang,
                    mode=trans_mode,
                    style=rewrite_style
                )

                cleaned_result = self.text_processor.clean_output(body, raw_result)
                final_result = self.text_processor.apply_spacing(cleaned_result, leading, trailing)

                if not privacy_mode:
                    self.cache.put(cache_key, cleaned_result)

                # Record in database if privacy mode is not enabled
                history_enabled = self.config.get("history_enabled", True)

                self.db.add_translation(
                    source_text=body,
                    translated_text=cleaned_result,
                    source_language=src_lang,
                    target_language=tgt_lang,
                    provider=active_provider_name,
                    privacy_mode=privacy_mode,
                    history_enabled=history_enabled
                )

                logger.info("Translation completed successfully on attempt %d", attempt + 1)
                return final_result

            except (AuthenticationError, RateLimitError) as e:
                # Do not retry authentication or rate limit errors
                logger.error("Non-retryable provider error: %s", e)
                raise
            except NetworkError as e:
                last_error = e
                if attempt < max_retries:
                    backoff = 2 ** attempt  # 1s, 2s
                    logger.warning("Network error on attempt %d: %s. Retrying in %ds...", attempt + 1, e, backoff)
                    time.sleep(backoff)
                else:
                    logger.error("Translation failed after %d retries due to network error", max_retries + 1)
                    raise
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    backoff = 2 ** attempt
                    logger.warning("Translation error on attempt %d: %s. Retrying in %ds...", attempt + 1, e, backoff)
                    time.sleep(backoff)
                else:
                    logger.error("Translation failed after %d retries: %s", max_retries + 1, e)
                    raise TranslationError(f"Translation failed: {e}") from e

        if last_error:
            raise TranslationError(f"Translation failed: {last_error}") from last_error
        return text


# Singleton instance
_translator_instance: Optional[TranslatorService] = None


def get_translator() -> TranslatorService:
    """Gets or initializes the global TranslatorService singleton."""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = TranslatorService()
    return _translator_instance
