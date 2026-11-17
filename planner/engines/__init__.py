"""Model engines. Each returns a CallResult so the orchestrator never cares which
vendor answered."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CallResult:
    text: str
    research_calls: int = 0
    cost_usd: float = 0.0


class EngineError(RuntimeError):
    pass


class UsageLimit(Exception):
    """Your Claude plan's usage limit was hit. Not retried; the run pauses."""

    def __init__(self, message: str, resets_at: int | None = None):
        super().__init__(message)
        self.resets_at = resets_at


def make_engine(kind: str, settings, workspace_root, mock: bool = False):
    if mock:
        from .mock_engine import MockEngine

        return MockEngine(kind)
    if kind == "claude":
        from .claude_engine import ClaudeEngine

        return ClaudeEngine(settings)
    if kind == "codex":
        from .codex_engine import CodexEngine

        return CodexEngine(settings)
    raise ValueError(f"unknown engine {kind!r}")
