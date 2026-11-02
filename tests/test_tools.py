from __future__ import annotations

from pathlib import Path

import pytest

from app.automation.registry import ToolRegistry
from app.automation.tools import register_default_tools
from app.config.settings import Settings
from app.memory.store import MemoryStore
from app.security.policy import SecurityPolicy


@pytest.fixture
def registry(tmp_path: Path) -> ToolRegistry:
    settings = Settings()
    settings.memory.db_path = str(tmp_path / "herb.db")
    settings.automation.allowed_roots = [str(tmp_path)]
    memory = MemoryStore(settings.memory.db_path)
    policy = SecurityPolicy(settings)
    reg = ToolRegistry(settings, policy, memory)
    register_default_tools(reg)
    return reg


@pytest.mark.asyncio
async def test_system_info(registry: ToolRegistry) -> None:
    result = await registry.execute("system_info", {})
    assert result.ok
    assert "CPU" in result.message


@pytest.mark.asyncio
async def test_create_file_requires_confirmation(registry: ToolRegistry, tmp_path: Path) -> None:
    target = tmp_path / "hello.txt"
    result = await registry.execute("create_file", {"path": str(target), "content": "oi"})
    assert result.requires_confirmation
    assert result.confirmation_token
    confirmed = await registry.execute(
        "create_file",
        {"path": str(target), "content": "oi"},
        confirmed=True,
        confirmation_token=result.confirmation_token,
    )
    assert confirmed.ok
    assert target.exists()


@pytest.mark.asyncio
async def test_unknown_tool(registry: ToolRegistry) -> None:
    result = await registry.execute("nao_existe", {})
    assert not result.ok


def test_catalog_contains_tools(registry: ToolRegistry) -> None:
    catalog = registry.catalog_text()
    assert "open_app" in catalog
    assert "delete_path" in catalog
