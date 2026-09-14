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

# Supported language codes and their display names
SUPPORTED_LANGUAGES: Dict[str, str] = {
    "auto": "Tự động phát hiện",
    "vi": "Tiếng Việt",
    "en": "Tiếng Anh",
    "zh-CN": "Tiếng Trung (Giản thể)",
    "zh-TW": "Tiếng Trung (Phồn thể)",
    "ja": "Tiếng Nhật",
    "ko": "Tiếng Hàn",
    "fr": "Tiếng Pháp",
    "de": "Tiếng Đức",
    "es": "Tiếng Tây Ban Nha",
    "th": "Tiếng Thái",
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

DEFAULT_CONFIG: Dict[str, Any] = {
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

    # Hotkeys
    "hotkeys": {
        "translate": {
            "key": "<ctrl>+<shift>+t",
            "enabled": True,
            "description": "Dịch văn bản bôi đen"
        },
        "translate_en": {
            "key": "<ctrl>+<shift>+e",
            "enabled": True,
            "description": "Dịch nhanh sang Tiếng Anh",
            "target": "en"
        },
        "translate_zh": {
            "key": "<ctrl>+<shift>+c",
            "enabled": True,
            "description": "Dịch nhanh sang Tiếng Trung",
            "target": "zh-CN"
        },
        "translate_ja": {
            "key": "<ctrl>+<shift>+j",
            "enabled": True,
            "description": "Dịch nhanh sang Tiếng Nhật",
            "target": "ja"
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
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    self._deep_update(self._data, saved_data)
                logger.info("Configuration loaded from %s", self.config_file)
            except Exception as e:
                logger.error("Failed to load config file, using defaults: %s", e)
        else:
            self.save()

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
