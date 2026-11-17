"""Claude Agent SDK engine (Muse, Warden, and the Synthesizer).

Security posture: the planner can only READ the run workspace and delegate to its two
researchers. Write/Edit/Bash are removed, and permission_mode="dontAsk" denies anything
not pre-approved instead of prompting.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
from pathlib import Path

import claude_agent_sdk
from claude_agent_sdk import (
    AgentDefinition,
    AssistantMessage,
    ClaudeAgentOptions,
    RateLimitEvent,
    ResultMessage,
    ToolUseBlock,
    query,
)

from . import CallResult, EngineError, UsageLimit

log = logging.getLogger("planner.claude")
LIMIT_TEXT = re.compile(r"usage limit|hit your limit|limit reached|rate.?limit|out of (extra )?usage", re.I)

READ_TOOLS = ["Read", "Grep", "Glob"]
RESEARCH_TOOLS = ["WebSearch", "WebFetch", "Read", "Grep", "Glob"]
BLOCKED_TOOLS = ["Bash", "Write", "Edit", "MultiEdit", "NotebookEdit", "KillShell"]
AGENT_TOOL_NAMES = {"Agent", "Task"}  # "Task" is the older name of the Agent tool


class ClaudeEngine:
    def __init__(self, settings):
        self.s = settings

    async def ask(
        self,
        *,
        system_prompt: str,
        prompt: str,
        cwd: str,
        persona=None,
        research_limit: int = 0,
        max_turns: int = 1,
        timeout_s: int = 300,
        model: str | None = None,
    ) -> CallResult:
        agents = None
        allowed = list(READ_TOOLS)
        if persona is not None and research_limit > 0:
            agents = {
                r.name: AgentDefinition(
                    description=r.description,
                    prompt=r.instructions,
                    tools=RESEARCH_TOOLS,
                    model=self.s.claude_research_model,
                    maxTurns=10,
                )
                for r in persona.researchers
            }
            # Pre-approve web tools too: with permission_mode="dontAsk" anything not in
            # allowed_tools is denied, including for the researchers.
            allowed += ["Agent", "WebSearch", "WebFetch"]
            prompt += (
                f"\n\n(You may call your research helpers at most {research_limit} "
                "time(s) in this turn, only if truly needed.)"
            )

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            model=model or self.s.claude_model,
            cwd=cwd,
            allowed_tools=allowed,
            disallowed_tools=BLOCKED_TOOLS,
            permission_mode="dontAsk",
            agents=agents,
            max_turns=max(1, max_turns),
            setting_sources=[],  # ignore any CLAUDE.md / settings on disk
        )

        async def _run() -> CallResult:
            text_parts: list[str] = []
            research = 0
            result: ResultMessage | None = None
            limit_hit: RateLimitEvent | None = None
            api_errors: list[str] = []
            async for msg in query(prompt=prompt, options=options):
                if isinstance(msg, RateLimitEvent):
                    info = msg.rate_limit_info
                    if info.status == "rejected":
                        limit_hit = msg
                    elif info.status == "allowed_warning" and info.utilization is not None:
                        log.warning("Claude plan usage at %.0f%% of the current window", info.utilization * 100)
                    continue
                if isinstance(msg, AssistantMessage) and msg.error:
                    api_errors.append(str(msg.error))
                if isinstance(msg, AssistantMessage) and msg.parent_tool_use_id is None:
                    for block in msg.content:
                        if isinstance(block, ToolUseBlock) and block.name in AGENT_TOOL_NAMES:
                            research += 1
                        elif hasattr(block, "text"):
                            text_parts.append(block.text)
                elif isinstance(msg, ResultMessage):
                    result = msg
            failed = result is None or result.is_error
            err_text = " ".join([*(result.errors or [] if result else []), (result.result or "") if failed and result else ""])
            if limit_hit is not None or (failed and ("rate_limit" in api_errors or LIMIT_TEXT.search(err_text))):
                resets = limit_hit.rate_limit_info.resets_at if limit_hit else None
                raise UsageLimit("Claude plan usage limit reached", resets)
            if result is None:
                raise EngineError("Claude returned no result")
            if result.is_error and not result.result:
                raise EngineError(f"Claude error: {result.subtype} {result.errors or ''}")
            if "authentication_failed" in api_errors:
                raise EngineError("Claude is not signed in. Run: start.bat --login-claude")
            text = result.result or (text_parts[-1] if text_parts else "")
            return CallResult(text=text, research_calls=research, cost_usd=result.total_cost_usd or 0.0)

        try:
            return await asyncio.wait_for(_run(), timeout=timeout_s)
        except asyncio.TimeoutError as e:
            raise EngineError(f"Claude call timed out after {timeout_s}s") from e

    async def close(self) -> None:
        return None


# ---------------------------------------------------------------- sign-in helpers
def bundled_cli() -> str:
    """Path to the Claude Code CLI that ships inside the claude-agent-sdk package."""
    base = Path(claude_agent_sdk.__file__).parent / "_bundled"
    for name in ("claude.exe", "claude"):
        if (base / name).exists():
            return str(base / name)
    return "claude"  # fall back to an installed Claude Code on PATH


def claude_login() -> None:
    """Interactive sign-in with your Claude subscription (opens a browser)."""
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    subprocess.run([bundled_cli(), "auth", "login", "--claudeai"], env=env, check=False)


def claude_auth_status() -> dict:
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    try:
        out = subprocess.run(
            [bundled_cli(), "auth", "status", "--json"], env=env, capture_output=True, text=True, timeout=60
        )
        return json.loads(out.stdout or "{}")
    except Exception as e:  # never block startup on a status check
        return {"error": str(e)}
