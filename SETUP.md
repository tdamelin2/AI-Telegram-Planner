# SETUP: everything to do before the first run

Work through this top to bottom. It takes about **20–30 minutes**. Tick each box as you go.

**Nothing here costs extra money.** Claude (Muse, Warden, Synthesizer) runs on your
**Claude Pro** plan and Codex (Forge, Axiom) on your **ChatGPT** plan. Runs use those plans'
usage limits instead of a pay-per-use API key.

---

## Overview

| # | Step | Time | Costs money? |
|---|------|------|--------------|
| 1 | Install Python | 5 min | No |
| 2 | (Optional) Keep the folder out of cloud sync | 2 min | No |
| 3 | Create 5 Telegram bots | 8 min | No |
| 4 | Turn off privacy for the Host bot | 1 min | No |
| 5 | Create the Telegram group | 2 min | No |
| 6 | Check how Claude is paid (nothing to buy) | 1 min | No |
| 7 | First `start.bat` run + fill in `.env` | 3 min | No |
| 8 | Find your chat id and user id | 2 min | No |
| 9 | Sign Claude and Codex in | 4 min | No |
| 10 | Free test runs (`--mock`) | 3 min | No |
| 11 | First real run | 10–20 min | No: uses your Pro and ChatGPT limits |

---

## Step 1: Install Python 3.10 or newer

- [ ] Open a terminal (Start → type `cmd` → Enter) and run:
  ```
  py --version
  ```
  If it prints `Python 3.10` or higher, skip to Step 2.
- [ ] Otherwise download Python **3.12 or 3.13** from https://www.python.org/downloads/windows/
- [ ] In the installer, **tick "Add python.exe to PATH"**, then click *Install Now*.
- [ ] Close the terminal, open a new one, and check `py --version` again.

## Step 2 (optional, recommended): Keep the folder out of cloud sync

If the project sits in a cloud-synced folder (OneDrive, Dropbox, iCloud Drive, or a synced
Desktop), note that the first run creates a `.venv` folder with thousands of files, plus `runs/`
logs, and the sync app will try to upload all of them. Pick one:

- [ ] **Move** the project folder somewhere that isn't synced, like `C:\Users\<you>\Projects\`, **or**
- [ ] Keep it where it is and accept the extra syncing. It still works.

> If you move it, do it now, before Step 7. The `.venv` breaks if you move it later.
> If that happens, delete `.venv` and run `start.bat` again.

## Step 3: Create 5 Telegram bots

In Telegram, open a chat with **@BotFather** (the official one, with the blue check).
Repeat this 5 times:

1. Send `/newbot`
2. Send a **display name** (what people see)
3. Send a **username**, which must end in `bot` and be unique worldwide
4. BotFather replies with a **token** like `1234567890:AAH...`. Copy it somewhere temporary.

| Bot | Suggested display name | Example username | Token goes in `.env` as |
|-----|------------------------|------------------|-------------------------|
| Host | 🧩 Planner Host | `my_planner_host_bot` | `HOST_BOT_TOKEN` |
| Muse | 🎨 Muse | `my_muse_bot` | `MUSE_BOT_TOKEN` |
| Warden | 🛡️ Warden | `my_warden_bot` | `WARDEN_BOT_TOKEN` |
| Forge | ⚙️ Forge | `my_forge_bot` | `FORGE_BOT_TOKEN` |
| Axiom | 📐 Axiom | `my_axiom_bot` | `AXIOM_BOT_TOKEN` |

- [ ] Host token saved
- [ ] Muse token saved
- [ ] Warden token saved
- [ ] Forge token saved
- [ ] Axiom token saved
- [ ] (Optional) Give each bot an avatar: `/setuserpic` → choose the bot → send a picture.
  This makes the group chat much easier to follow.

> 🔒 A token is a password. Anyone who has it controls that bot. Don't paste tokens in chats
> or screenshots. If one leaks, use `/revoke` in BotFather and put the new token in `.env`.

## Step 4: Turn off privacy for the Host bot (Host only)

By default, a bot in a group only sees messages addressed to it. The Host needs to see
`/plan` captions on files you upload.

- [ ] In @BotFather send `/setprivacy` → choose the **Host** bot → choose **Disable**.
- [ ] Leave privacy **on** for Muse, Warden, Forge and Axiom. They only post and never need to read.

> Do this **before** adding the Host to the group. If the Host is already in the group,
> remove it and add it back. The privacy change only applies when the bot joins.

## Step 5: Create the Telegram group

- [ ] Telegram → *New Group* → name it something like **"🧠 Planner Room"**.
- [ ] Add all 5 bots by searching their usernames.
- [ ] You are already in it as the creator.
- [ ] Send any message in the group (e.g. `hello`) so the group shows up in Step 8.

> No admin rights needed: the bots don't read each other (the orchestrator relays
> everything), so Telegram's bot-to-bot mode isn't used.

## Step 6: Check how Claude is paid (nothing to buy)

The project is set to **`CLAUDE_AUTH=plan`**, so the Claude planners sign in with your
**Claude Pro** account and use your Pro usage limits. You don't need an API key or credit.

- [ ] Nothing to do here. You'll sign in during Step 9.

Good to know:
- Planner runs share the **same usage limits as your normal Claude chats**. A big run
  leaves less for chatting until your limit resets.
- If a run hits your limit, it **pauses** (nothing is lost) and the Host posts:
  *"⏸️ Your Claude Pro usage limit was reached… send /resume <run_id>"*.
- To save usage, the defaults already use **Sonnet** (not Opus) and **2 critique rounds**.
- Want pay-per-use instead? Set `CLAUDE_AUTH=api` and fill in `ANTHROPIC_API_KEY` from
  console.anthropic.com. This is billed separately from Pro, with a $15-per-run cap.

## Step 7: First `start.bat` run, then fill in `.env`

- [ ] Open the project folder and **double-click `start.bat`**.
  - The first run creates `.venv` and installs the packages (1–3 minutes).
  - Then it creates `.env` and opens it in Notepad.
- [ ] Fill in these lines and **save**:
  ```
  HOST_BOT_TOKEN=...
  MUSE_BOT_TOKEN=...
  WARDEN_BOT_TOKEN=...
  FORGE_BOT_TOKEN=...
  AXIOM_BOT_TOKEN=...
  ```
- [ ] Leave `CLAUDE_AUTH=plan` as it is, and leave `ANTHROPIC_API_KEY` empty.
- [ ] Leave `TELEGRAM_CHAT_ID` and `ALLOWED_USER_IDS` empty for now (Step 8 fills them in).
- [ ] Leave `OPENAI_API_KEY` empty if you want Codex to use your ChatGPT plan (Step 9).
  Fill it in only if you'd rather pay OpenAI per token.

> If Windows shows "Windows protected your PC" for `start.bat`, click *More info → Run anyway*.
> The file is plain text, and you can open it in Notepad to check what it does.

## Step 8: Find your chat id and user id

- [ ] Open a terminal **in the project folder** (in File Explorer, click the address
  bar, type `cmd`, press Enter) and run:
  ```
  start.bat --whoami
  ```
- [ ] While it's listening (90 seconds), send a message in the **Planner group**
  (e.g. `hi`), and one more in a **private chat with the Host bot**.
- [ ] It prints lines like:
  ```
  chat: Planner Room  TELEGRAM_CHAT_ID=-1001234567890   from tdamelin  user id=123456789
  ```
- [ ] Put the numbers into `.env`:
  ```
  TELEGRAM_CHAT_ID=-1001234567890
  ALLOWED_USER_IDS=123456789
  ```
  The group id is the **negative** number. Your user id is the positive one.

> Nothing printed? The Host still has privacy on (redo Step 4, including remove and re-add),
> or send `/start@your_host_bot` in the group instead.
> If Telegram ever "upgrades" the group, its id changes. Rerun `--whoami` if commands stop working.

## Step 9: Sign Claude and Codex in

**9a: Claude (your Pro account)**
- [ ] In the terminal (in the project folder) run:
  ```
  start.bat --login-claude
  ```
- [ ] A browser opens. Sign in with the **same account that has Claude Pro** and approve.
- [ ] It should print `Claude signed in ✅`.

> This sign-in is saved in your Windows user profile, the same place Claude Code keeps
> its login. If you already use Claude Code on this laptop, you may already be signed in.

**9b: Codex (your ChatGPT account)**
- [ ] Run:
  ```
  start.bat --login-codex
  ```
- [ ] A browser opens. Sign in with your ChatGPT account and approve.
  (If you put an `OPENAI_API_KEY` in `.env`, it uses that instead and no browser opens.)
- [ ] It should print `Codex login complete.`
- [ ] If Windows asks for permission to set up the Codex sandbox, allow it. That sandbox keeps
  Forge and Axiom read-only.

> The Codex login is stored only in `codex_home\auth.json` inside the project. Your normal
> Codex setup in `%USERPROFILE%\.codex` is not touched. Don't share or commit `auth.json`.

## Step 10: Free test runs (no AI costs)

**10a: Pipeline test in the terminal**
- [ ] Run:
  ```
  start.bat plan inbox\example.md --mock
  ```
- [ ] You'll see the whole flow with fake AIs: drafts → critiques → revisions → scores →
  Phase 2 → synthesis. At the prompt, type `a` and press Enter to approve.
- [ ] Check that `outputs\example_PLAN.md` exists.

**10b: Telegram test (still free)**
- [ ] Run:
  ```
  start.bat --mock
  ```
- [ ] In the group you should see the Host say **"🟢 Planner online"**, then a roll call from
  all four bots. ✅ This confirms all 5 tokens work.
- [ ] In the group send: `/plan example.md`
- [ ] Watch the mock debate play out from the four different bots, then send `/approve`.
- [ ] Also try `/status`, `/runs` and `/help`.
- [ ] Press **Ctrl+C** in the terminal to stop.

If both pass, setup is done. ✅

## Step 11: First real run (uses your plan limits)

- [ ] The defaults are already tuned for Pro (Sonnet, 2 critique rounds). Nothing to change.
- [ ] Start it with **`start.bat`** (double-click). The terminal should show no ⚠️ sign-in warnings.
- [ ] In the group, either:
  - send the small `inbox\example.md` file as an attachment with caption `/plan`, or
  - type `/plan example.md`
- [ ] Watch for these on the first real run:
  - [ ] All four planners post a **📝 Draft**. If one posts ⚠️ failed, check `runs\planner.log`.
  - [ ] **Forge and Axiom use their researchers.** This is the one part that couldn't be tested
    before going live. If they never seem to, copy the 4 files from `codex_home\agents\` into
    `%USERPROFILE%\.codex\agents\` and try again.
  - [ ] After the run, check **claude.ai → Settings → Usage** to see how much of your Pro
    limit one run used. That tells you how many runs fit per window.
- [ ] If you see **⏸️ usage limit reached**, wait for the reset time it shows, then `/resume <run_id>`.
- [ ] Review the draft plan file the Host posts, then `/approve` or `/revise <notes>`.

---

## Final pre-flight checklist

- [ ] `py --version` shows 3.10+
- [ ] 5 bots created; Host privacy **disabled**; all 5 in the group
- [ ] `.env` has: `CLAUDE_AUTH=plan`, 5 tokens, `TELEGRAM_CHAT_ID`, `ALLOWED_USER_IDS`
- [ ] `start.bat --login-claude` printed "Claude signed in ✅"
- [ ] `start.bat --login-codex` printed "login complete"
- [ ] Mock terminal test produced `outputs\example_PLAN.md`
- [ ] Mock Telegram test showed the roll call from all 4 bots

## Keep private (never share or upload)

`.env` · `codex_home\auth.json` · `runs\` (contains your documents) · `outputs\`

## Quick command reference

| Command | Purpose |
|---------|---------|
| `start.bat` | Start everything (Telegram mode) |
| `start.bat --mock` | Telegram mode with fake AIs (free) |
| `start.bat plan inbox\file.md` | Plan one file in the terminal, no Telegram |
| `start.bat --resume <run_id>` | Resume a run in the terminal |
| `start.bat --whoami` | Find chat id / user id |
| `start.bat --login-claude` | Sign Claude in with your Pro account |
| `start.bat --login-codex` | Sign Codex in for this project |
