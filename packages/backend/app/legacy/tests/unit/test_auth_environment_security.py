import pytest

from utils.get_env import (
    is_disable_auth_enabled,
    is_presenton_electron_desktop,
)


@pytest.mark.parametrize(
    "disable_auth",
    ["true", "1", "yes", "on"],
)
def test_server_cannot_disable_authentication(monkeypatch, disable_auth):
    monkeypatch.setenv("DISABLE_AUTH", disable_auth)
    monkeypatch.delenv("PRESENTON_ELECTRON", raising=False)

    assert is_disable_auth_enabled() is False


@pytest.mark.parametrize(
    "electron_value",
    ["1", "yes", "on", "TRUE", "True"],
)
def test_non_exact_electron_marker_cannot_disable_auth(
    monkeypatch, electron_value
):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    monkeypatch.setenv("PRESENTON_ELECTRON", electron_value)

    assert is_presenton_electron_desktop() is False
    assert is_disable_auth_enabled() is False


def test_electron_can_disable_authentication(monkeypatch):
    monkeypatch.setenv("DISABLE_AUTH", "true")
    monkeypatch.setenv("PRESENTON_ELECTRON", "true")

    assert is_presenton_electron_desktop() is True
    assert is_disable_auth_enabled() is True


def test_electron_with_auth_enabled_keeps_authentication(
    monkeypatch,
):
    monkeypatch.setenv("DISABLE_AUTH", "false")
    monkeypatch.setenv("PRESENTON_ELECTRON", "true")

    assert is_disable_auth_enabled() is False


def test_electron_without_disable_auth_keeps_authentication(
    monkeypatch,
):
    monkeypatch.delenv("DISABLE_AUTH", raising=False)
    monkeypatch.setenv("PRESENTON_ELECTRON", "true")

    assert is_disable_auth_enabled() is False