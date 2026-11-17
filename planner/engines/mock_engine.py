"""Fake engine for a free dry run: `python run.py plan inbox/example.md --mock`.

It answers every prompt with plausible JSON or Markdown so you can test the whole
pipeline (Telegram included) without spending any tokens.
"""
from __future__ import annotations

import asyncio
import json
import random
import re

from . import CallResult


class MockEngine:
    def __init__(self, kind: str):
        self.kind = kind

    async def ask(self, *, system_prompt: str, prompt: str, persona=None, **_) -> CallResult:
        await asyncio.sleep(0.05)
        who = persona.name if persona else "Synthesizer"
        tag = re.search(r"\[TASK:(\w+)\]", prompt)
        task = tag.group(1) if tag else "free"
        labels = re.findall(r"### Proposal ([A-D])", prompt)
        if task == "draft":
            body = {
                "summary": f"{who}'s mock plan.",
                "proposal_md": f"## Approach\n{who} approach.\n## Steps\n1. Do it.\n"
                "## Tools & Stack\nPython\n## Security\nSecrets in .env\n## Why This Wins\nMock.",
            }
        elif task == "critique":
            own = re.search(r"Your own proposal is ([A-D])", prompt)
            own_l = own.group(1) if own else None
            body = {
                "summary": f"{who} critiqued.",
                "reviews": [
                    {
                        "label": lab,
                        "creative": random.randint(5, 9),
                        "efficient": random.randint(5, 9),
                        "secure": random.randint(5, 9),
                        "strengths": ["clear"],
                        "problems": ["vague step 2"],
                        "must_fix": [],
                    }
                    for lab in labels
                    if lab != own_l
                ],
                "veto": [],
            }
        elif task == "revise":
            changed = random.random() < 0.5
            body = {
                "summary": f"{who} {'revised' if changed else 'held'}.",
                "changed": changed,
                "changes": [{"what": "clarified step 2", "because": "vague step 2"}] if changed else [],
                "proposal_md": f"## Approach\n{who} revised approach.",
            }
        elif task == "floor":
            body = {
                "action": random.choice(["speak", "speak", "pass"]),
                "addressed_to": random.choice(["all", "Muse", "Warden", "Forge", "Axiom"]),
                "idea_type": "yes_and",
                "message": f"{who}: what if we added a playful onboarding tour?",
            }
        elif task == "review":
            body = {"approve": True, "blockers": [], "summary": "Looks safe."}
        else:  # synth / fix / human revision -> markdown
            return CallResult(text="# Mock Plan\n\n## Summary\nMock synthesized plan.\n\n## Dissent Log\nNone.")
        return CallResult(text=json.dumps(body))

    async def close(self) -> None:
        return None
