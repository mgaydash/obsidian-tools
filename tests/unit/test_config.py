"""Unit tests for lib/config.py"""

import json
from pathlib import Path

import pytest

from lib import config


@pytest.fixture
def xdg_config(tmp_path, monkeypatch):
    """Point config storage at a temp XDG_CONFIG_HOME and return the file path."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "obsidian-tools" / "config.json"


# ---------------------------------------------------------------------------
# get_config_path
# ---------------------------------------------------------------------------

def test_get_config_path_uses_xdg(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config.get_config_path() == tmp_path / "obsidian-tools" / "config.json"


def test_get_config_path_falls_back_to_home(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    assert config.get_config_path() == tmp_path / ".config" / "obsidian-tools" / "config.json"


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------

def test_load_config_missing_returns_empty(xdg_config):
    assert not xdg_config.exists()
    assert config.load_config() == {}


def test_load_config_malformed_returns_empty(xdg_config):
    xdg_config.parent.mkdir(parents=True, exist_ok=True)
    xdg_config.write_text("{ this is not valid json")
    assert config.load_config() == {}


def test_load_config_non_dict_returns_empty(xdg_config):
    xdg_config.parent.mkdir(parents=True, exist_ok=True)
    xdg_config.write_text(json.dumps(["a", "b"]))
    assert config.load_config() == {}


def test_load_config_valid(xdg_config):
    xdg_config.parent.mkdir(parents=True, exist_ok=True)
    xdg_config.write_text(json.dumps({"vault_path": "/vault"}))
    assert config.load_config() == {"vault_path": "/vault"}


# ---------------------------------------------------------------------------
# save_config
# ---------------------------------------------------------------------------

def test_save_config_creates_dir_and_file(xdg_config):
    returned = config.save_config({"vault_path": "/vault"})

    assert returned == xdg_config
    assert xdg_config.is_file()
    # Round-trips and ends with a trailing newline
    text = xdg_config.read_text()
    assert json.loads(text) == {"vault_path": "/vault"}
    assert text.endswith("\n")


def test_save_config_overwrites_existing(xdg_config):
    config.save_config({"vault_path": "/one"})
    config.save_config({"vault_path": "/two"})
    assert config.load_config() == {"vault_path": "/two"}


# ---------------------------------------------------------------------------
# set_value / get_value
# ---------------------------------------------------------------------------

def test_set_value_persists(xdg_config):
    returned = config.set_value("vault_path", "/vault")
    assert returned == xdg_config
    assert config.get_value("vault_path") == "/vault"


def test_set_value_preserves_other_keys(xdg_config):
    config.save_config({"existing": "keep"})
    config.set_value("vault_path", "/vault")
    loaded = config.load_config()
    assert loaded == {"existing": "keep", "vault_path": "/vault"}


def test_get_value_returns_default_when_missing(xdg_config):
    assert config.get_value("vault_path") is None
    assert config.get_value("vault_path", "/fallback") == "/fallback"
