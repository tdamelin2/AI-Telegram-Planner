"""All tunable settings and caps in one place.

Values can be overridden in .env (same names). Defaults are the recommended caps.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "runs"
INBOX_DIR = ROOT / "inbox"
OUTPUTS_DIR = ROOT / "outputs"
CODEX_HOME = ROOT / "codex_home"


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


def _ids(name: str) -> set[int]:
    raw = os.getenv(name, "")
    return {int(x) for x in raw.replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()}


@dataclass(frozen=True)
class Settings:
    # --- Claude sign-in -------------------------------------------------
    claude_auth: str  # "plan" = your Claude subscription login, "api" = ANTHROPIC_API_KEY

    # --- Models -----------------------------------------------------------
    claude_model: str  # alias ("opus", "sonnet") or full model id
    claude_research_model: str
    synth_model: str
    codex_model: str | None  # None = your Codex account default

    # --- Telegram -----------------------------------------------------------
    host_token: str | None
    chat_id: int | None
    allowed_user_ids: set[int]
    telegram_min_gap_s: float  # per bot per chat; 3.2s keeps each bot under 20 msg/min

    # --- Phase 1: structured debate ---------------------------------------
    p1_max_critique_rounds: int
    p1_proposal_max_words: int
    p1_call_timeout_s: int
    p1_max_turns: int  # Claude tool round trips per call (research included)

    # --- Phase 2: creativity floor (global caps) -------------------------
    p2_max_total_messages: int
    p2_window_s: int
    p2_call_timeout_s: int

    # --- Synthesis / review ------------------------------------------------
    max_human_revisions: int
    synth_timeout_s: int

    # --- Safety --------------------------------------------------------------
    max_input_bytes: int
    claude_budget_usd_per_run: float  # stop Claude calls past this estimate (api mode only)


def load_settings() -> Settings:
    chat = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    auth = os.getenv("CLAUDE_AUTH", "plan").strip().lower()
    return Settings(
        claude_auth=auth if auth in ("plan", "api") else "plan",
        claude_model=os.getenv("CLAUDE_MODEL", "sonnet"),
        claude_research_model=os.getenv("CLAUDE_RESEARCH_MODEL", "sonnet"),
        synth_model=os.getenv("SYNTH_MODEL", "sonnet"),
        codex_model=os.getenv("CODEX_MODEL") or None,
        host_token=os.getenv("HOST_BOT_TOKEN") or None,
        chat_id=int(chat) if chat.lstrip("-").isdigit() else None,
        allowed_user_ids=_ids("ALLOWED_USER_IDS"),
        telegram_min_gap_s=_float("TELEGRAM_MIN_GAP_S", 3.2),
        p1_max_critique_rounds=_int("P1_MAX_CRITIQUE_ROUNDS", 2),
        p1_proposal_max_words=_int("P1_PROPOSAL_MAX_WORDS", 900),
        p1_call_timeout_s=_int("P1_CALL_TIMEOUT_S", 420),
        p1_max_turns=_int("P1_MAX_TURNS", 12),
        p2_max_total_messages=_int("P2_MAX_TOTAL_MESSAGES", 12),
        p2_window_s=_int("P2_WINDOW_S", 600),
        p2_call_timeout_s=_int("P2_CALL_TIMEOUT_S", 180),
        max_human_revisions=_int("MAX_HUMAN_REVISIONS", 2),
        synth_timeout_s=_int("SYNTH_TIMEOUT_S", 600),
        max_input_bytes=_int("MAX_INPUT_BYTES", 400_000),
        claude_budget_usd_per_run=_float("CLAUDE_BUDGET_USD_PER_RUN", 15.0),
    )


# Rubric used for scoring proposals (weights must sum to 1).
RUBRIC_WEIGHTS = {"creative": 1 / 3, "efficient": 1 / 3, "secure": 1 / 3}
