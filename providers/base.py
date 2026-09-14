"""Abstract Base Class for Translation Providers."""

from abc import ABC, abstractmethod


class TranslationError(Exception):
    """Base exception for translation failures."""
    pass


class AuthenticationError(TranslationError):
    """Raised when API key or credentials are missing or invalid."""
    pass


class NetworkError(TranslationError):
    """Raised on connection timeout or network unavailability."""
    pass


class RateLimitError(TranslationError):
    """Raised when provider rate limit / quota is exceeded."""
    pass


class TranslationProvider(ABC):
    """Interface for translation providers."""

    @abstractmethod
    def translate(
        self,
        text: str,
        source_language: str,
        target_language: str,
        mode: str = "translate",
        style: str = "natural"
    ) -> str:
        """Translates or rewrites text from source_language to target_language.

        Args:
            text: The text to translate or rewrite.
            source_language: Source language code (e.g., 'vi', 'en', 'auto').
            target_language: Target language code (e.g., 'en', 'ja').
            mode: 'translate' or 'rewrite'.
            style: Rewrite style ('natural', 'formal', 'casual', 'polish').

        Returns:
            The translated or rewritten text string.

        Raises:
            TranslationError, AuthenticationError, NetworkError, RateLimitError
        """
        raise NotImplementedError
