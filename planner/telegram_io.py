"""Telegram as the stage: each persona posts through its own bot, the Host bot receives
your commands. Bots never need to read each other (the orchestrator relays everything),
so no bot-to-bot mode or admin rights are required.

Uses the plain Bot API over HTTPS with long polling, so it works from a laptop with no
public URL. Plain text only (no parse_mode) so model output can never break formatting.
"""
from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path

import httpx

API = "https://api.telegram.org"
MAX_LEN = 3900  # Telegram limit is 4096 chars; leave headroom

# httpx logs full URLs at INFO, and Bot API URLs contain the token. Keep it quiet.
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("planner.telegram")


def _split(text: str) -> list[str]:
    text = text.strip() or "(empty)"
    parts: list[str] = []
    while len(text) > MAX_LEN:
        cut = text.rfind("\n", 0, MAX_LEN)
        if cut < MAX_LEN // 2:
            cut = MAX_LEN
        parts.append(text[:cut])
        text = text[cut:].lstrip("\n")
    parts.append(text)
    return parts


class _Bot:
    def __init__(self, key: str, token: str, min_gap: float):
        self.key = key
        self.token = token
        self.min_gap = min_gap
        self.username = "?"
        self._lock = asyncio.Lock()
        self._last = 0.0


class TelegramIO:
    def __init__(self, settings, persona_tokens: dict[str, str]):
        self.s = settings
        self.chat_id = settings.chat_id
        self.bots: dict[str, _Bot] = {
            k: _Bot(k, t, settings.telegram_min_gap_s) for k, t in persona_tokens.items()
        }
        host_token = settings.host_token or next(iter(persona_tokens.values()))
        self.bots["host"] = _Bot("host", host_token, settings.telegram_min_gap_s)
        self.http = httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=15.0))
        self._offset = 0

    # ---------------------------------------------------------------- low level
    async def _call(self, bot: _Bot, method: str, **kwargs):
        for attempt in range(5):
            try:
                r = await self.http.post(f"{API}/bot{bot.token}/{method}", **kwargs)
            except httpx.HTTPError as e:
                log.warning("telegram %s network error (%s), retrying", method, type(e).__name__)
                await asyncio.sleep(2 + attempt * 2)
                continue
            data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
            if data.get("ok"):
                return data["result"]
            if r.status_code == 429:
                wait = int(data.get("parameters", {}).get("retry_after", 5)) + 1
                log.warning("telegram rate limit on %s bot, waiting %ss", bot.key, wait)
                await asyncio.sleep(wait)
                continue
            raise RuntimeError(f"Telegram {method} failed for {bot.key}: {data.get('description', r.status_code)}")
        raise RuntimeError(f"Telegram {method} failed after retries")

    async def _throttle(self, bot: _Bot):
        wait = bot.min_gap - (time.monotonic() - bot._last)
        if wait > 0:
            await asyncio.sleep(wait)
        bot._last = time.monotonic()

    # ---------------------------------------------------------------- public
    async def start(self) -> dict[str, str]:
        names = {}
        for key, bot in self.bots.items():
            me = await self._call(bot, "getMe")
            bot.username = me.get("username", "?")
            names[key] = bot.username
        # Make sure long polling works (a webhook would block getUpdates).
        await self._call(self.bots["host"], "deleteWebhook", json={"drop_pending_updates": False})
        return names

    async def post(self, who: str, text: str, chat_id: int | None = None) -> None:
        bot = self.bots.get(who, self.bots["host"])
        target = chat_id or self.chat_id
        if target is None:
            return
        async with bot._lock:
            for part in _split(text):
                await self._throttle(bot)
                await self._call(
                    bot,
                    "sendMessage",
                    json={"chat_id": target, "text": part, "disable_web_page_preview": True},
                )

    async def send_document(self, who: str, path: Path, caption: str = "") -> None:
        bot = self.bots.get(who, self.bots["host"])
        if self.chat_id is None:
            return
        async with bot._lock:
            await self._throttle(bot)
            with open(path, "rb") as f:
                await self._call(
                    bot,
                    "sendDocument",
                    data={"chat_id": str(self.chat_id), "caption": caption[:1000]},
                    files={"document": (path.name, f.read(), "text/markdown")},
                )

    async def get_updates(self) -> list[dict]:
        host = self.bots["host"]
        try:
            updates = await self._call(
                host,
                "getUpdates",
                json={"offset": self._offset, "timeout": 30, "allowed_updates": ["message"]},
                timeout=45.0,
            )
        except RuntimeError as e:
            log.warning("%s", e)
            await asyncio.sleep(5)
            return []
        if updates:
            self._offset = updates[-1]["update_id"] + 1
        return updates

    async def download(self, file_id: str, max_bytes: int) -> bytes:
        host = self.bots["host"]
        info = await self._call(host, "getFile", json={"file_id": file_id})
        if info.get("file_size", 0) > max_bytes:
            raise ValueError(f"file is larger than {max_bytes} bytes")
        r = await self.http.get(f"{API}/file/bot{host.token}/{info['file_path']}")
        r.raise_for_status()
        return r.content[:max_bytes]

    async def close(self) -> None:
        await self.http.aclose()


class ConsoleIO:
    """Same interface as TelegramIO but prints to the terminal (terminal mode)."""

    def __init__(self, labels: dict[str, str]):
        self.labels = labels

    async def start(self):
        return {}

    async def post(self, who: str, text: str, chat_id=None) -> None:
        print(f"\n{self.labels.get(who, '🧩 Host')}\n{text}\n", flush=True)

    async def send_document(self, who: str, path: Path, caption: str = "") -> None:
        print(f"\n📄 {caption}\n   -> {path}\n", flush=True)

    async def close(self) -> None:
        return None


class TeeIO:
    """Post to Telegram and echo to the console."""

    def __init__(self, tg: TelegramIO, console: ConsoleIO):
        self.tg, self.console = tg, console

    async def post(self, who, text, chat_id=None):
        await self.console.post(who, text)
        try:
            await self.tg.post(who, text, chat_id)
        except Exception as e:  # never let a chat hiccup kill a run
            log.error("telegram post failed: %s", e)

    async def send_document(self, who, path, caption=""):
        await self.console.send_document(who, path, caption)
        try:
            await self.tg.send_document(who, path, caption)
        except Exception as e:
            log.error("telegram document failed: %s", e)
