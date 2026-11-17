"""Every prompt the orchestrator sends. The [TASK:x] tag is used by the mock engine."""
from __future__ import annotations

from .personas.base import COMMON_FORMAT_NOTE

RUBRIC = """Scoring rubric (1-10 each):
- creative: original, delightful, avoids the boring default where it matters
- efficient: least effort/cost/complexity for the result; realistic for one person
- secure: protects secrets, data and users; safe defaults; handles failure"""


def draft(doc_block: str, max_words: int) -> str:
    return f"""[TASK:draft]
PHASE 1, ROUND 0: BLIND DRAFT. You cannot see the other planners' work.

Read the document and propose the best way to carry out the project or plan it
describes. Be the most creative, efficient and secure version of YOUR perspective.
{COMMON_FORMAT_NOTE} Max {max_words} words.

{doc_block}

Reply with JSON only:
{{"summary": "<= 40 words for the group chat",
  "proposal_md": "<your full proposal in Markdown>"}}"""


def critique(doc_block: str, proposals: dict[str, str], own_label: str, is_warden: bool, round_no: int) -> str:
    blocks = "\n\n".join(f"### Proposal {lab}\n{text}" for lab, text in sorted(proposals.items()))
    veto = (
        '\n  "veto": [{"label": "X", "reason": "...", "lift_if": "exact change that would lift it"}],'
        "\nUse veto ONLY for serious security problems. Empty list if none."
        if is_warden
        else '\n  "blocking_concerns": [{"label": "X", "reason": "what must change before X is acceptable"}],'
        "\nUse blocking_concerns only for problems that MUST be fixed. Empty list if none."
        " You cannot veto; only Warden can."
    )
    return f"""[TASK:critique]
PHASE 1, CRITIQUE ROUND {round_no}. Proposals are anonymous. Your own proposal is {own_label};
do NOT review it. Review every other proposal honestly from your perspective.

{RUBRIC}

Source document (for checking requirements):
{doc_block}

{blocks}

Reply with JSON only:
{{"summary": "<= 40 words for the group chat",
  "reviews": [{{"label": "A", "creative": 7, "efficient": 6, "secure": 8,
               "strengths": ["..."], "problems": ["..."], "must_fix": ["..."]}}],{veto}
  "best_idea_to_steal": "one idea from another proposal worth keeping"}}"""


def revise(doc_block: str, own_proposal: str, feedback: list[dict], max_words: int) -> str:
    lines = []
    for fb in feedback:
        if fb.get("veto") or fb.get("concern"):
            continue
        lines.append(
            f"- Reviewer {fb['reviewer']}: scores c{fb.get('creative')}/e{fb.get('efficient')}/s{fb.get('secure')}; "
            f"problems: {fb.get('problems')}; must_fix: {fb.get('must_fix')}"
        )
    vetoes = [fb for fb in feedback if fb.get("veto")]
    veto_txt = "\n".join(
        f"- SECURITY VETO: {v['veto'].get('reason')} (lift if: {v['veto'].get('lift_if')})" for v in vetoes
    ) or "- none"
    concerns = "\n".join(
        f"- Reviewer {fb['reviewer']}: {fb['concern']}" for fb in feedback if fb.get("concern")
    ) or "- none"
    return f"""[TASK:revise]
PHASE 1, REVISION. Here is anonymous feedback on YOUR proposal.

Evidence rule: change something ONLY if the feedback gives a concrete reason you accept.
If you disagree, keep your position and say why in "held_because". Never cave to
pressure alone. A security veto must be addressed or explicitly argued against.
Blocking concerns must each be fixed, or answered in "held_because" with your reason.

Feedback:
{chr(10).join(lines)}
Blocking concerns:
{concerns}
Vetoes:
{veto_txt}

Your current proposal:
{own_proposal}

Source document:
{doc_block}

Reply with JSON only (max {max_words} words in proposal_md):
{{"summary": "<= 40 words for the group chat",
  "changed": true,
  "changes": [{{"what": "...", "because": "the specific reason/evidence"}}],
  "held_because": ["points you kept and why"],
  "proposal_md": "<full updated proposal in Markdown>"}}"""


def floor(
    leader_md: str,
    others_summary: str,
    transcript: list[dict],
    me_name: str,
    msgs_left: int,
    research_left: int,
    max_words: int,
    is_warden: bool,
) -> str:
    convo = "\n".join(
        f"#{m['n']} {m['who']} -> {m['to']}: {m['text']}" for m in transcript
    ) or "(nobody has spoken yet: you open the floor)"
    warden_rule = (
        "\nYou may NOT veto here. Make risky ideas safe instead of killing them."
        if is_warden
        else ""
    )
    return f"""[TASK:floor]
PHASE 2: CREATIVITY FLOOR. Phase 1 picked a leading plan. Now improve it with bold,
creative ideas in a fast group conversation.

Rules:
- "Yes, and...": build on others, twist an idea, or bring a genuinely new one.
- No plain agreement and no repeating what was said. If you have nothing new, PASS.
- At least once in the conversation, someone should propose a WILD idea.
- Address a specific planner by name if you want their reaction.
- Max {max_words} words. You have {msgs_left} message(s) and {research_left} research call(s) left.{warden_rule}

Leading plan from Phase 1:
{leader_md}

Other proposals (summaries):
{others_summary}

Conversation so far:
{convo}

You are {me_name}. Reply with JSON only:
{{"action": "speak" or "pass",
  "addressed_to": "all" or "Muse" or "Warden" or "Forge" or "Axiom",
  "idea_type": "new" or "yes_and" or "twist" or "wild",
  "message": "your message"}}"""


def synthesize(doc_block: str, leader_label: str, proposals: dict[str, dict], scores_md: str,
               vetoes_md: str, floor_md: str) -> str:
    props = "\n\n".join(
        f"### Proposal {lab} (by {p['author']})\n{p['text']}" for lab, p in sorted(proposals.items())
    )
    return f"""[TASK:synth]
You are the SYNTHESIZER. Four planners debated (Phase 1) and brainstormed (Phase 2).
Write the final plan Markdown. Start from the leading proposal ({leader_label}), merge the
best compatible ideas from the others and from Phase 2, and keep it executable.

Rules:
- Do NOT smooth over disagreement. Record every unresolved disagreement in "Dissent Log"
  with who argued what. tdamelin decides those.
- Every security veto must be either fixed in the plan or listed as "⛔ Unresolved veto".
- Only include Phase 2 ideas that are compatible with the plan; list rejected ones briefly.
- No invented facts. Keep claims as specific as the planners made them.

Required sections, in order:
# <Project name>: Final Plan
## Summary
## Chosen Approach (and why it won)
## Architecture / Structure
## Step-by-Step Execution Checklist   (numbered, each step checkable)
## Security Requirements
## Creative Additions (from Phase 2)
## Efficiency Notes
## Risks & Mitigations
## Dissent Log
## Open Questions for tdamelin
## Scorecard

Source document:
{doc_block}

Scores (average from other planners):
{scores_md}

Security vetoes:
{vetoes_md}

Phase 2 conversation:
{floor_md}

All final proposals:
{props}

Reply with the Markdown plan only."""


def warden_review(plan_md: str) -> str:
    return f"""[TASK:review]
FINAL SECURITY REVIEW of the synthesized plan. Approve unless there is a serious,
concrete security problem. For each blocker give the exact fix.

{plan_md}

Reply with JSON only:
{{"approve": true, "summary": "<= 40 words", "blockers": [{{"issue": "...", "fix": "..."}}]}}"""


def fix_blockers(plan_md: str, blockers: list[dict]) -> str:
    items = "\n".join(f"- {b.get('issue')} -> fix: {b.get('fix')}" for b in blockers)
    return f"""[TASK:fix]
Warden blocked the plan for these security issues:
{items}

Update the plan to fix them. If a fix is impossible without tdamelin's decision, keep the
issue in the Dissent Log as "⛔ Unresolved veto". Keep every other section intact.
Reply with the full updated Markdown plan only.

{plan_md}"""


def human_revision(plan_md: str, notes: str) -> str:
    return f"""[TASK:human]
tdamelin reviewed the plan and asked for these changes:
<tim_notes>
{notes}
</tim_notes>
Apply them faithfully. Keep the required section structure and the Dissent Log.
Reply with the full updated Markdown plan only.

{plan_md}"""
