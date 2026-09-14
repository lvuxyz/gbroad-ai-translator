"""Configuration manager for Windows AI Translation Tool.

Handles application settings, default hotkeys, supported languages,
and secure storage of API keys via Windows Credential Manager (keyring).
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional
import keyring
from dotenv import load_dotenv
from utils.logger import get_logger

load_dotenv()
logger = get_logger()

SERVICE_NAME = "AITranslator"

# Supported language codes and their display names.
# Vietnamese and English lead the list because they are the pair this tool is
# built around; the rest follow alphabetically by Vietnamese name.
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "auto": "Tự động phát hiện",
    "vi": "Tiếng Việt",
    "en": "Tiếng Anh",
    "ar": "Tiếng Ả Rập",
    "pl": "Tiếng Ba Lan",
    "fa": "Tiếng Ba Tư",
    "bn": "Tiếng Bengal",
    "pt": "Tiếng Bồ Đào Nha",
    "bg": "Tiếng Bulgaria",
    "cs": "Tiếng Séc",
    "da": "Tiếng Đan Mạch",
    "de": "Tiếng Đức",
    "he": "Tiếng Do Thái",
    "et": "Tiếng Estonia",
    "nl": "Tiếng Hà Lan",
    "ko": "Tiếng Hàn",
    "hi": "Tiếng Hindi",
    "hu": "Tiếng Hungary",
    "el": "Tiếng Hy Lạp",
    "is": "Tiếng Iceland",
    "id": "Tiếng Indonesia",
    "km": "Tiếng Khmer",
    "lo": "Tiếng Lào",
    "lv": "Tiếng Latvia",
    "lt": "Tiếng Litva",
    "ms": "Tiếng Mã Lai",
    "my": "Tiếng Miến Điện",
    "no": "Tiếng Na Uy",
    "ne": "Tiếng Nepal",
    "ru": "Tiếng Nga",
    "ja": "Tiếng Nhật",
    "ro": "Tiếng Romania",
    "fr": "Tiếng Pháp",
    "fi": "Tiếng Phần Lan",
    "sr": "Tiếng Serbia",
    "si": "Tiếng Sinhala",
    "sk": "Tiếng Slovakia",
    "sl": "Tiếng Slovenia",
    "sw": "Tiếng Swahili",
    "ta": "Tiếng Tamil",
    "es": "Tiếng Tây Ban Nha",
    "te": "Tiếng Telugu",
    "th": "Tiếng Thái",
    "tr": "Tiếng Thổ Nhĩ Kỳ",
    "sv": "Tiếng Thụy Điển",
    "zh-CN": "Tiếng Trung (Giản thể)",
    "zh-TW": "Tiếng Trung (Phồn thể)",
    "uk": "Tiếng Ukraina",
    "ur": "Tiếng Urdu",
    "gu": "Tiếng Gujarat",
    "kn": "Tiếng Kannada",
    "ml": "Tiếng Malayalam",
    "mr": "Tiếng Marathi",
    "pa": "Tiếng Punjab",
    "af": "Tiếng Afrikaans",
    "cy": "Tiếng Wales",
    "it": "Tiếng Ý",
}

# Languages offered without the "auto detect" pseudo-entry
TARGET_LANGUAGES: Dict[str, str] = {
    code: name for code, name in SUPPORTED_LANGUAGES.items() if code != "auto"
}

# Supported providers
PROVIDERS = {
    "google": "Google Translate (Miễn phí, tức thì)",
    "gemini": "Google Gemini (Cần API Key)",
    "openai": "OpenAI ChatGPT (Cần API Key)",
}

# Default models per provider
DEFAULT_MODELS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "google": "google-translate-v2",
}

# AI Rewrite styles
REWRITE_STYLES = [
    "natural",
    "formal",
    "casual",
    "polish",
]

# Bumped whenever saved settings need rewriting on load (see ConfigManager._migrate)
CONFIG_VERSION = 2

# Hotkeys shipped before v2. They collided with Chrome's "reopen closed tab",
# DevTools, and VS Code panels, so installs still carrying them are migrated.
LEGACY_DEFAULT_HOTKEYS: Dict[str, str] = {
    "translate": "<ctrl>+<shift>+t",
    "translate_en": "<ctrl>+<shift>+e",
    "translate_zh": "<ctrl>+<shift>+c",
    "translate_ja": "<ctrl>+<shift>+j",
}

DEFAULT_CONFIG: Dict[str, Any] = {
    "config_version": CONFIG_VERSION,

    # General
    "first_run": True,
    "start_with_windows": False,
    "minimize_to_tray": True,
    "restore_clipboard": True,
    "show_notifications": True,
    "privacy_mode": False,
    "history_enabled": True,

    # Translation
    "source_language": "auto",
    "target_language": "en",
    "provider": "google",
    "mode": "translate",  # "translate" | "rewrite"
    "rewrite_style": "natural",

    # Models
    "gemini_model": "gemini-2.5-flash",
    "openai_model": "gpt-4o-mini",

    # Two-way translation: one hotkey sends primary -> secondary and back again,
    # choosing the direction from the text itself.
    "auto_swap": {
        "enabled": True,
        "primary": "vi",
        "secondary": "en",
    },

    # Per-application overrides, keyed by lower-cased executable name.
    # Any of target_language, mode, rewrite_style and skip_code may be set.
    "app_profiles": {},

    # Terms that must survive translation unchanged.
    # Rows: {"term": str, "replacement": str, "match_case": bool, "enabled": bool}
    "glossary": [],

    # Show the result for confirmation instead of replacing the selection outright
    "preview_popup": {
        "enabled": False,
        "timeout_seconds": 12,
    },

    # Screen-region OCR translation
    "ocr": {
        "enabled": True,
        "language": "auto",
    },

    # Most recently used target languages, so the tray menu stays usable
    "recent_languages": ["en", "vi", "ja"],

    # Hotkeys
    "hotkeys": {
        "translate": {
            "key": "<ctrl>+<alt>+t",
            "enabled": True,
            "description": "Dịch văn bản bôi đen"
        },
        "translate_en": {
            "key": "<ctrl>+<alt>+e",
            "enabled": True,
            "description": "Dịch nhanh sang Tiếng Anh",
            "target": "en"
        },
        "translate_zh": {
            "key": "<ctrl>+<alt>+c",
            "enabled": True,
            "description": "Dịch nhanh sang Tiếng Trung",
            "target": "zh-CN"
        },
        "translate_ja": {
            "key": "<ctrl>+<alt>+j",
            "enabled": True,
            "description": "Dịch nhanh sang Tiếng Nhật",
            "target": "ja"
        },
        "translate_ocr": {
            "key": "<ctrl>+<alt>+o",
            "enabled": True,
            "description": "Dịch vùng màn hình (OCR)",
            "action": "ocr"
        },
    }
}


class ConfigManager:
    """Manages application settings and Windows Credential Manager API keys."""

    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            app_data = os.getenv("APPDATA")
            if app_data:
                self.config_dir = Path(app_data) / "AITranslator"
            else:
                self.config_dir = Path(__file__).resolve().parent
        else:
            self.config_dir = config_dir

        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.config_dir / "config.json"
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Loads configuration from JSON file or initializes defaults."""
        self._data = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy defaults

        if self.config_file.exists():
            # Read from the file rather than the merged result: defaults already
            # carry the current version, which would mask every older file.
            saved_version = 1
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    saved_version = saved_data.get("config_version", 1)
                    self._deep_update(self._data, saved_data)
                logger.info("Configuration loaded from %s", self.config_file)
            except Exception as e:
                logger.error("Failed to load config file, using defaults: %s", e)
                saved_version = CONFIG_VERSION  # Defaults are already current
            self._migrate(saved_version)
        else:
            self.save()

    def _migrate(self, saved_version: int) -> None:
        """Rewrites settings saved by an older version of the application."""
        if saved_version >= CONFIG_VERSION:
            return

        changed = False

        # v1 -> v2: retire the Ctrl+Shift hotkeys. They were never suppressed, so
        # the foreground application acted on them too. Only untouched defaults
        # are rewritten; a combination the user chose themselves is left alone.
        if saved_version < 2:
            for name, legacy_key in LEGACY_DEFAULT_HOTKEYS.items():
                entry = self._data.get("hotkeys", {}).get(name)
                if entry and entry.get("key") == legacy_key:
                    entry["key"] = DEFAULT_CONFIG["hotkeys"][name]["key"]
                    changed = True
                    logger.info(
                        "Migrated hotkey '%s' from %s to %s", name, legacy_key, entry["key"]
                    )

        self._data["config_version"] = CONFIG_VERSION
        self.save()
        if changed:
            logger.info("Configuration migrated to version %d", CONFIG_VERSION)

    def save(self) -> None:
        """Saves current configuration to JSON file."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)
            logger.info("Configuration successfully saved to %s", self.config_file)
        except Exception as e:
            logger.error("Failed to save configuration: %s", e)

    def _deep_update(self, base_dict: dict, update_dict: dict) -> None:
        """Recursively merges saved settings over defaults."""
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict and isinstance(base_dict[key], dict):
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieves a top-level configuration value."""
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Sets a top-level configuration value and saves."""
        self._data[key] = value
        self.save()

    # --- Hotkey helpers ---
    def get_hotkeys(self) -> Dict[str, Any]:
        """Returns the hotkey definitions."""
        return self._data.get("hotkeys", {})

    def set_hotkey(self, name: str, key_combo: str, enabled: bool = True) -> None:
        """Updates a specific hotkey combo and state."""
        if "hotkeys" not in self._data:
            self._data["hotkeys"] = {}
        if name in self._data["hotkeys"]:
            self._data["hotkeys"][name]["key"] = key_combo
            self._data["hotkeys"][name]["enabled"] = enabled
        else:
            self._data["hotkeys"][name] = {"key": key_combo, "enabled": enabled}
        self.save()

    # --- Feature helpers ---
    def get_glossary(self) -> list:
        """Returns the raw glossary rows."""
        return self._data.get("glossary", [])

    def get_app_profiles(self) -> Dict[str, Any]:
        """Returns per-application overrides keyed by executable name."""
        return self._data.get("app_profiles", {})

    def get_auto_swap(self) -> Dict[str, Any]:
        """Returns the two-way translation pair settings."""
        return self._data.get("auto_swap", DEFAULT_CONFIG["auto_swap"])

    def remember_language(self, code: str, limit: int = 6) -> None:
        """Moves a language to the front of the recently-used list."""
        if not code or code == "auto":
            return
        recent = [c for c in self._data.get("recent_languages", []) if c != code]
        recent.insert(0, code)
        self._data["recent_languages"] = recent[:limit]
        self.save()

    # --- API Key Management (Windows Credential Manager) ---
    def get_api_key(self, provider: str) -> Optional[str]:
        """Gets API key from Windows Credential Manager or environment variables."""
        key_name = f"{provider.lower()}_api_key"

        # 1. Try Windows Credential Manager
        try:
            stored_key = keyring.get_password(SERVICE_NAME, key_name)
            if stored_key:
                return stored_key.strip()
        except Exception as e:
            logger.warning("Keyring lookup failed for %s: %s", provider, e)

        # 2. Fallback to environment variables
        env_map = {
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "google": "GOOGLE_API_KEY",
        }
        env_var = env_map.get(provider.lower())
        if env_var and os.getenv(env_var):
            return os.getenv(env_var, "").strip()

        return None

    def set_api_key(self, provider: str, api_key: str) -> bool:
        """Saves API key to Windows Credential Manager."""
        key_name = f"{provider.lower()}_api_key"
        try:
            if api_key:
                keyring.set_password(SERVICE_NAME, key_name, api_key.strip())
            else:
                try:
                    keyring.delete_password(SERVICE_NAME, key_name)
                except keyring.errors.PasswordDeleteError:
                    pass
            logger.info("API key for provider '%s' updated in Windows Credential Manager", provider)
            return True
        except Exception as e:
            logger.error("Failed to store API key in keyring for %s: %s", provider, e)
            return False

    def reset_defaults(self) -> None:
        """Resets all settings to default values."""
        self._data = json.loads(json.dumps(DEFAULT_CONFIG))
        self.save()


# Singleton instance
_config_instance: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """Gets or initializes the global ConfigManager singleton."""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager()
    return _config_instance
