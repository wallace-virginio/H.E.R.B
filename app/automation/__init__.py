"""Automação Windows e registro de ferramentas."""

from .registry import ToolRegistry, ToolResult
from .tools import register_default_tools

__all__ = ["ToolRegistry", "ToolResult", "register_default_tools"]
