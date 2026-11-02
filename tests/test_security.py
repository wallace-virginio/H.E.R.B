from __future__ import annotations

from app.config.settings import AuthLevel, Settings
from app.security.policy import SecurityPolicy


def test_simple_action_allowed() -> None:
    policy = SecurityPolicy(Settings())
    result = policy.classify("open_app", {"name": "calc"}, AuthLevel.SIMPLE)
    assert result.allowed
    assert not result.requires_confirmation


def test_modify_requires_confirmation() -> None:
    policy = SecurityPolicy(Settings())
    result = policy.classify("create_file", {"path": r"C:\Users\test\a.txt", "content": "x"}, AuthLevel.MODIFY)
    assert result.allowed
    assert result.requires_confirmation


def test_shell_blocked() -> None:
    policy = SecurityPolicy(Settings())
    result = policy.classify("run_shell", {"cmd": "dir"}, AuthLevel.CRITICAL)
    assert not result.allowed


def test_dangerous_pattern_blocked() -> None:
    policy = SecurityPolicy(Settings())
    result = policy.classify("delete_path", {"path": "rm -rf C:\\"}, AuthLevel.CRITICAL)
    assert not result.allowed


def test_system_path_blocked() -> None:
    policy = SecurityPolicy(Settings())
    result = policy.classify("open_path", {"path": r"C:\Windows\System32"}, AuthLevel.SIMPLE)
    assert not result.allowed
