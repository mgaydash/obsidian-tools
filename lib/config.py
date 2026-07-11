"""Persistent user configuration for Obsidian Tools.

Config is stored as JSON at ``$XDG_CONFIG_HOME/obsidian-tools/config.json``
(falling back to ``~/.config/obsidian-tools/config.json``). The file is
machine-written but human-readable/editable.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

APP_NAME = "obsidian-tools"


def get_config_path() -> Path:
    """Return the path to the config file, respecting XDG_CONFIG_HOME."""
    base = os.environ.get("XDG_CONFIG_HOME")
    config_dir = Path(base) if base else Path.home() / ".config"
    return config_dir / APP_NAME / "config.json"


def load_config() -> Dict[str, Any]:
    """Load the persisted config, returning {} if missing or unreadable."""
    path = get_config_path()
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(config: Dict[str, Any]) -> Path:
    """Persist config as JSON, creating the config directory if needed.

    Returns the path the config was written to.
    """
    path = get_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def set_value(key: str, value: Any) -> Path:
    """Set a single config key and persist. Returns the config file path."""
    config = load_config()
    config[key] = value
    return save_config(config)


def get_value(key: str, default: Optional[Any] = None) -> Any:
    """Return a single config value, or ``default`` if unset."""
    return load_config().get(key, default)
