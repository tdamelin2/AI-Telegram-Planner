"""OpenAI Codex SDK engine (Forge and Axiom).

Codex runs with CODEX_HOME pointed at ./codex_home, so it loads this project's
config.toml and the four researcher TOMLs in codex_home/agents/ without touching
your personal ~/.codex folder.

Security posture: read-only sandbox, approvals denied (nothing can escalate).
"""
from __future__ import annotations

import asyncio

from openai_codex import ApprovalMode, AsyncCodex, CodexConfig, Sandbox

from ..config import CODEX_HOME
from . import CallResult, EngineError


def codex_config() -> CodexConfig:
    return CodexConfig(env={"CODEX_HOME": str(CODEX_HOME)})


def _count_spawns(items) -> int:
    n = 0
    for item in items or []:
        root = getattr(item, "root", item)
        if getattr(root, "type", None) != "collabAgentToolCall":
            continue
        tool = getattr(root, "tool", None)
        if getattr(tool, "value", tool) == "spawnAgent":
            n += max(1, len(getattr(root, "receiver_thread_ids", []) or []))
    return n


class CodexEngine:
    def __init__(self, settings):
        self.s = settings
        self._codex: AsyncCodex | None = None
        self._lock = asyncio.Lock()

    async def _client(self) -> AsyncCodex:
        async with self._lock:
            if self._codex is None:
                codex = AsyncCodex(codex_config())
                await codex.__aenter__()
                self._codex = codex
            return self._codex

    async def ask(
        self,
        *,
        system_prompt: str,
        prompt: str,
        cwd: str,
        persona=None,
        research_limit: int = 0,
        max_turns: int = 1,  # unused by Codex; kept for a shared interface
        timeout_s: int = 300,
        model: str | None = None,
    ) -> CallResult:
        if persona is not None and research_limit > 0:
            names = ", ".join(f"`{r.name}`" for r in persona.researchers)
            prompt += (
                f"\n\n(Research helpers available as custom agents: {names}. "
                f"If evidence is truly needed, you may spawn at most {research_limit} of "
                "them by name and wait for their results. Do not spawn any other agents.)"
            )
        else:
            prompt += "\n\n(Do not spawn any subagents for this turn.)"

        codex = await self._client()

        async def _run() -> CallResult:
            thread = await codex.thread_start(
                cwd=cwd,
                developer_instructions=system_prompt,
                model=model or self.s.codex_model,
                sandbox=Sandbox.read_only,
                approval_mode=ApprovalMode.deny_all,
                ephemeral=True,
            )
            result = await thread.run(prompt)
            if result.error is not None and not result.final_response:
                raise EngineError(f"Codex error: {result.error}")
            return CallResult(
                text=result.final_response or "",
                research_calls=_count_spawns(result.items),
            )

        try:
            return await asyncio.wait_for(_run(), timeout=timeout_s)
        except asyncio.TimeoutError as e:
            raise EngineError(f"Codex call timed out after {timeout_s}s") from e

    async def close(self) -> None:
        if self._codex is not None:
            try:
                await self._codex.__aexit__(None, None, None)
            finally:
                self._codex = None


async def codex_login(api_key: str | None = None) -> None:
    """One-time login stored in codex_home/auth.json."""
    async with AsyncCodex(codex_config()) as codex:
        acct = await codex.account()
        if acct.account is not None:
            print("Codex is already logged in for this project.")
            return
        if api_key:
            await codex.login_api_key(api_key)
            print("Codex logged in with OPENAI_API_KEY.")
            return
        handle = await codex.login_chatgpt()
        print("\nOpen this link to sign in to ChatGPT for Codex:\n", handle.auth_url, "\n")
        try:
            import webbrowser

            webbrowser.open(handle.auth_url)
        except Exception:
            pass
        await handle.wait()
        print("Codex login complete.")


async def codex_logged_in() -> bool:
    async with AsyncCodex(codex_config()) as codex:
        acct = await codex.account()
        return acct.account is not None or not acct.requires_openai_auth
