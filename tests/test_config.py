"""Tests for API configuration module."""

import os

import pytest

from memorygym.config import APIConfig, get_api_config


class TestGetApiConfig:
    def test_explicit_key_and_url(self):
        cfg = get_api_config(api_key="sk-test", api_url="https://example.com")
        assert cfg.api_key == "sk-test"
        assert cfg.api_url == "https://example.com"

    def test_chutes_key_from_env(self, monkeypatch):
        monkeypatch.setenv("CHUTES_API_KEY", "sk-chutes")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("API_KEY", raising=False)
        cfg = get_api_config()
        assert cfg.api_key == "sk-chutes"

    def test_openai_key_fallback(self, monkeypatch):
        monkeypatch.delenv("CHUTES_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        monkeypatch.delenv("API_KEY", raising=False)
        cfg = get_api_config()
        assert cfg.api_key == "sk-openai"

    def test_api_key_fallback(self, monkeypatch):
        monkeypatch.delenv("CHUTES_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("API_KEY", "sk-generic")
        cfg = get_api_config()
        assert cfg.api_key == "sk-generic"

    def test_explicit_key_overrides_env(self, monkeypatch):
        monkeypatch.setenv("CHUTES_API_KEY", "sk-env")
        cfg = get_api_config(api_key="sk-explicit")
        assert cfg.api_key == "sk-explicit"

    def test_no_key_raises(self, monkeypatch):
        monkeypatch.delenv("CHUTES_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("API_KEY", raising=False)
        with pytest.raises(RuntimeError, match="No API key"):
            get_api_config()

    def test_default_url(self, monkeypatch):
        monkeypatch.delenv("API_URL", raising=False)
        cfg = get_api_config(api_key="sk-test")
        assert "chutes.ai" in cfg.api_url

    def test_env_url_override(self, monkeypatch):
        monkeypatch.setenv("API_URL", "https://custom.api/v1")
        cfg = get_api_config(api_key="sk-test")
        assert cfg.api_url == "https://custom.api/v1"

    def test_config_is_frozen(self):
        cfg = get_api_config(api_key="sk-test")
        with pytest.raises(AttributeError):
            cfg.api_key = "modified"
