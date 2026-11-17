"""Entry point logic: Telegram mode, terminal mode, login and helper commands."""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .config import INBOX_DIR, OUTPUTS_DIR, ROOT, RUNS_DIR, load_settings

load_dotenv(ROOT / ".env")

# Plan mode: make sure an API key in the environment can't silently switch Claude to
# pay-per-use billing. The SDK then uses your Claude sign-in (start.bat --login-claude).
if os.getenv("CLAUDE_AUTH", "plan").strip().lower() != "api":
    os.environ.pop("ANTHROPIC_API_KEY", None)

from .engines import make_engine  # noqa: E402
from .orchestrator import Run, new_run  # noqa: E402
from .personas import ROSTER  # noqa: E402
from .telegram_io import ConsoleIO, TeeIO, TelegramIO  # noqa: E402

log = logging.getLogger("planner")

HELP = """🧠 Telegram Planner commands
/plan: send an .md file with caption /plan (or reply /plan to an .md file)
/plan <name.md>: plan a file from the inbox folder
/status: current run status
/approve: accept the draft plan
/revise <notes>: ask for changes to the draft
/stop: stop the current run (it can be resumed)
/resume <run_id>: continue a stopped or crashed run
/runs: list recent runs
/help: this message"""


def setup_logging() -> None:
    RUNS_DIR.mkdir(exist_ok=True)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # emojis on Windows consoles
        except Exception:
            pass
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.FileHandler(RUNS_DIR / "planner.log", encoding="utf-8"), logging.StreamHandler()],
    )


def build_engines(settings, mock: bool):
    claude = make_engine("claude", settings, None, mock)
    engines = {}
    for p in ROSTER:
        # Codex gets one app-server per persona; Claude calls are independent anyway.
        engines[p.key] = claude if p.engine == "claude" else make_engine("codex", settings, None, mock)
    return engines, claude


def labels() -> dict[str, str]:
    d = {p.key: p.label for p in ROSTER}
    d["host"] = "🧩 Host"
    return d


async def preflight(settings, mock: bool) -> list[str]:
    if mock:
        return []
    problems = []
    if settings.claude_auth == "api":
        if not os.getenv("ANTHROPIC_API_KEY"):
            problems.append("CLAUDE_AUTH=api but ANTHROPIC_API_KEY is empty in .env.")
    else:
        from .engines.claude_engine import claude_auth_status

        st = await asyncio.to_thread(claude_auth_status)
        if "error" in st:
            problems.append(f"Couldn't check the Claude sign-in ({st['error']}).")
        elif not st.get("loggedIn"):
            problems.append("Claude is not signed in. Run:  start.bat --login-claude")
    try:
        from .engines.codex_engine import codex_logged_in

        if not await codex_logged_in():
            problems.append("Codex is not logged in for this project. Run:  start.bat --login-codex")
    except Exception as e:
        problems.append(f"Codex could not start ({e}). Check the openai-codex install.")
    return problems


# ====================================================================== terminal mode
async def terminal_run(path: Path | None, resume: str | None, mock: bool) -> None:
    settings = load_settings()
    for p in await preflight(settings, mock):
        print("⚠️ ", p)
    if resume:
        run_dir = RUNS_DIR / resume
        if not run_dir.exists():
            print(f"No run named {resume}")
            return
    else:
        text = path.read_text(encoding="utf-8")
        run_dir = new_run(text, path.name)

    async def decide():
        ans = await asyncio.to_thread(input, "\n[a]pprove / [r]evise <notes> / [s]top > ")
        ans = ans.strip()
        if ans.lower().startswith("a"):
            return ("approve", None)
        if ans.lower().startswith("r"):
            return ("revise", ans[1:].lstrip("evise").strip() or "Tighten and clarify.")
        return ("stop", None)

    engines, synth = build_engines(settings, mock)
    io = ConsoleIO(labels())
    await Run(run_dir, io, engines, synth, settings, decide, asyncio.Event()).execute()


# ====================================================================== telegram mode
class Bot:
    def __init__(self, settings, mock: bool):
        self.s = settings
        self.mock = mock
        tokens = {p.key: os.getenv(p.token_env, "").strip() for p in ROSTER}
        missing = [ROSTER[i].token_env for i, t in enumerate(tokens.values()) if not t]
        if missing:
            raise SystemExit(f"Missing bot tokens in .env: {', '.join(missing)}")
        if settings.chat_id is None:
            raise SystemExit("TELEGRAM_CHAT_ID is missing in .env. Run: python run.py --whoami")
        if not settings.allowed_user_ids:
            raise SystemExit("ALLOWED_USER_IDS is missing in .env. Run: python run.py --whoami")
        self.tg = TelegramIO(settings, tokens)
        self.io = TeeIO(self.tg, ConsoleIO(labels()))
        self.task: asyncio.Task | None = None
        self.run: Run | None = None
        self.decisions: asyncio.Queue = asyncio.Queue()
        self.cancel = asyncio.Event()

    async def start(self) -> None:
        names = await self.tg.start()
        print("\nBots online:")
        for key, user in names.items():
            print(f"  {labels().get(key, key):<12} @{user}")
        for p in await preflight(self.s, self.mock):
            print("⚠️ ", p)
            await self.io.post("host", f"⚠️ {p}")
        await self.io.post("host", "🟢 Planner online. Roll call:")
        for p in ROSTER:
            await self.io.post(p.key, f"{p.label} ready: {p.role}")
        await self.io.post("host", HELP)
        print("\nListening for commands in Telegram. Press Ctrl+C to quit.\n")
        while True:
            for upd in await self.tg.get_updates():
                msg = upd.get("message")
                if msg:
                    try:
                        await self.handle(msg)
                    except Exception as e:
                        log.exception("command failed")
                        await self.io.post("host", f"⚠️ Command failed: {e}")

    def busy(self) -> bool:
        return self.task is not None and not self.task.done()

    async def handle(self, msg: dict) -> None:
        user = (msg.get("from") or {}).get("id")
        chat = (msg.get("chat") or {}).get("id")
        text = (msg.get("text") or msg.get("caption") or "").strip()
        if not text.startswith("/"):
            return
        if user not in self.s.allowed_user_ids or chat not in (self.s.chat_id, user):
            log.warning("ignored command from user %s in chat %s", user, chat)
            return
        cmd, _, arg = text.partition(" ")
        cmd = cmd.split("@")[0].lower()
        arg = arg.strip()

        if cmd in ("/help", "/start"):
            await self.io.post("host", HELP)
        elif cmd == "/plan":
            await self.cmd_plan(msg, arg)
        elif cmd == "/resume":
            await self.cmd_resume(arg)
        elif cmd == "/status":
            await self.cmd_status()
        elif cmd == "/runs":
            runs = sorted(RUNS_DIR.glob("*/state.json"), reverse=True)[:5]
            lines = [f"{p.parent.name}: {json.loads(p.read_text(encoding='utf-8')).get('status')}" for p in runs]
            await self.io.post("host", "Recent runs:\n" + ("\n".join(lines) or "(none)"))
        elif cmd == "/stop":
            if self.busy():
                self.cancel.set()
                await self.decisions.put(("stop", None))
                await self.io.post("host", "Stopping after the current step…")
        elif cmd in ("/approve", "/revise") and not (
            self.busy() and self.run and self.run.state.get("status") == "awaiting_approval"
        ):
            await self.io.post("host", "There is no draft waiting for approval yet.")
        elif cmd == "/approve":
            await self.decisions.put(("approve", None))
        elif cmd == "/revise":
            if not arg:
                await self.io.post("host", "Add your notes: /revise make step 3 cheaper")
            else:
                await self.decisions.put(("revise", arg))
        else:
            await self.io.post("host", "Unknown command. /help")

    async def cmd_plan(self, msg: dict, arg: str) -> None:
        if self.busy():
            await self.io.post("host", "A run is already in progress. /status or /stop first.")
            return
        doc = msg.get("document") or (msg.get("reply_to_message") or {}).get("document")
        if doc:
            name = Path(doc.get("file_name") or "plan.md").name
            if not name.lower().endswith((".md", ".markdown", ".txt")):
                await self.io.post("host", "Please send a Markdown (.md) file.")
                return
            data = await self.tg.download(doc["file_id"], self.s.max_input_bytes)
            text = data.decode("utf-8", errors="replace")
        elif arg:
            path = (INBOX_DIR / Path(arg).name)  # only the inbox folder, no path tricks
            if not path.exists():
                await self.io.post("host", f"Not found in inbox: {path.name}")
                return
            name, text = path.name, path.read_text(encoding="utf-8")[: self.s.max_input_bytes]
        else:
            await self.io.post("host", "Send an .md file with caption /plan, or /plan <file in inbox>.")
            return
        self.launch(new_run(text, name))

    async def cmd_resume(self, run_id: str) -> None:
        if self.busy():
            await self.io.post("host", "A run is already in progress.")
            return
        run_dir = RUNS_DIR / Path(run_id).name
        if not run_id or not (run_dir / "state.json").exists():
            await self.io.post("host", "Usage: /resume <run_id>  (see /runs)")
            return
        self.launch(run_dir)

    async def cmd_status(self) -> None:
        if not self.busy() or not self.run:
            await self.io.post("host", "Idle. Send /plan to start.")
            return
        st = self.run.state
        done = [k for k in st["steps"] if not k.endswith("_posted") and not k.startswith("labels")]
        p2 = st.get("p2", {})
        await self.io.post(
            "host",
            f"Run {st['run_id']}: {st['status']}\nSteps done: {', '.join(done) or 'none'}\n"
            f"Phase 2 messages: {len(p2.get('transcript', []))}\n{self.run.cost_line()}",
        )

    def launch(self, run_dir: Path) -> None:
        self.cancel = asyncio.Event()
        self.decisions = asyncio.Queue()
        engines, synth = build_engines(self.s, self.mock)
        self.run = Run(run_dir, self.io, engines, synth, self.s, self.decisions.get, self.cancel)
        self.task = asyncio.create_task(self.run.execute())


async def telegram_main(mock: bool) -> None:
    bot = Bot(load_settings(), mock)
    try:
        await bot.start()
    finally:
        await bot.tg.close()


# ====================================================================== helpers
async def whoami() -> None:
    import httpx

    token = os.getenv("HOST_BOT_TOKEN") or os.getenv("MUSE_BOT_TOKEN")
    if not token:
        print("Put HOST_BOT_TOKEN (or MUSE_BOT_TOKEN) in .env first.")
        return
    print("Send any message in your planner group (and one in a private chat with the host bot).")
    print("Listening for 90 seconds…\n")
    seen = set()
    offset = 0
    async with httpx.AsyncClient(timeout=40) as http:
        await http.post(f"https://api.telegram.org/bot{token}/deleteWebhook")
        for _ in range(3):
            r = await http.post(
                f"https://api.telegram.org/bot{token}/getUpdates", json={"offset": offset, "timeout": 30}
            )
            for u in r.json().get("result", []):
                offset = u["update_id"] + 1
                m = u.get("message") or u.get("my_chat_member") or {}
                chat, frm = m.get("chat", {}), m.get("from", {})
                key = (chat.get("id"), frm.get("id"))
                if key not in seen:
                    seen.add(key)
                    print(f"chat: {chat.get('title') or chat.get('username') or 'private'}  "
                          f"TELEGRAM_CHAT_ID={chat.get('id')}   from {frm.get('first_name')}  user id={frm.get('id')}")
    if not seen:
        print("No messages seen. Is the bot in the group, and did you message it?")
    else:
        print("\nPut the group's TELEGRAM_CHAT_ID and your user id (ALLOWED_USER_IDS) in .env.")


def main() -> None:
    setup_logging()
    for d in (INBOX_DIR, OUTPUTS_DIR, RUNS_DIR):
        d.mkdir(exist_ok=True)
    ap = argparse.ArgumentParser(description="Four-AI Telegram planner")
    ap.add_argument("command", nargs="?", choices=["plan"], help="'plan' = run one MD in the terminal")
    ap.add_argument("file", nargs="?", help="MD file for terminal mode")
    ap.add_argument("--resume", metavar="RUN_ID", help="resume a run (terminal mode)")
    ap.add_argument("--mock", action="store_true", help="fake AIs: test everything for free")
    ap.add_argument("--login-codex", action="store_true", help="one-time Codex sign-in for this project")
    ap.add_argument("--login-claude", action="store_true", help="sign in with your Claude subscription")
    ap.add_argument("--whoami", action="store_true", help="find your chat id and user id")
    a = ap.parse_args()

    if a.login_claude:
        from .engines.claude_engine import claude_auth_status, claude_login

        claude_login()
        st = claude_auth_status()
        print("Claude signed in ✅" if st.get("loggedIn") else f"Claude sign-in not confirmed: {st}")
    elif a.login_codex:
        from .engines.codex_engine import codex_login

        asyncio.run(codex_login(os.getenv("OPENAI_API_KEY") or None))
    elif a.whoami:
        asyncio.run(whoami())
    elif a.command == "plan" or a.resume:
        if not a.resume and not a.file:
            ap.error("plan needs a file, e.g.  python run.py plan inbox/example.md")
        try:
            asyncio.run(terminal_run(Path(a.file) if a.file else None, a.resume, a.mock))
        except KeyboardInterrupt:
            print("\nStopped. Resume with: python run.py --resume <run_id>")
    else:
        try:
            asyncio.run(telegram_main(a.mock))
        except KeyboardInterrupt:
            print("\nPlanner stopped.")
