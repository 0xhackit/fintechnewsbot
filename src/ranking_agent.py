"""
AI-powered ranking agent: determines article tier and platform eligibility.

Replaces scattered score thresholds and the should_post_to_x() AI gate
with one authoritative ranking step.
"""

import json
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

RANKING_MODEL = "claude-haiku-4-5-20251001"

RANKING_PROMPT = """You are a fintech news editor deciding the tier and platform eligibility for an article.

ARTICLE:
Title: {title}
Snippet: {snippet}
Automated Score: {score}/100
Score Breakdown: {score_breakdown}

TIER DEFINITIONS:
- **high** (post to Telegram + X): Product launches by major institutions, significant regulatory actions, funding rounds >$50M, major partnerships between well-known companies, infrastructure milestones
- **medium** (Telegram only): Crypto-native company news, smaller funding rounds, infrastructure updates, notable integrations
- **low** (Telegram only if score >= 50): Minor updates, commentary with substance, smaller company news
- **reject**: Promotional content, listicles, generic tech unrelated to fintech, price speculation, marketing slogans, ecosystem recaps, engagement bait

IMPORTANT: Evaluate whether the automated score bonuses are justified. For example:
- institution_bonus=20 for a commentary piece that merely mentions a bank should be "low" not "high"
- financial_bonus=40 for a "$X billion market" statistic in a generic article should be discounted
- tier1 pattern matches on promotional tweets (e.g., "launches campaign") are not real product launches

Respond with ONLY valid JSON (no markdown):
{{
  "tier": "high" or "medium" or "low" or "reject",
  "reason": "one sentence explaining your decision",
  "post_to_telegram": true or false,
  "post_to_x": true or false,
  "category": "payments|crypto|banking|regulation|tokenization|stablecoins|defi|infrastructure|other"
}}"""


def _format_feedback_section(feedback: dict) -> str:
    """Format feedback examples for injection into the ranking prompt."""
    signals = feedback.get("signals", [])
    rules = feedback.get("learned_rules", [])

    if not signals and not rules:
        return ""

    lines = ["\nUSER PREFERENCES (learn from these):"]

    # Positive examples
    positive = [s for s in signals if s.get("signal") == "positive"]
    if positive:
        lines.append("\nLIKED (post more like these):")
        for s in positive[-5:]:
            reason = s.get("reason", "liked")
            lines.append(f'- "{s["title"]}" [{s.get("category", "other")}] — {reason}')

    # Negative examples
    negative = [s for s in signals if s.get("signal") == "negative"]
    if negative:
        lines.append("\nDISLIKED (reject or lower tier on ALL platforms):")
        for s in negative[-5:]:
            reason = s.get("reason", "disliked")
            lines.append(f'- "{s["title"]}" [{s.get("category", "other")}] — {reason}')

    # Promoted to X
    promoted = [s for s in positive if s.get("reason") == "promoted_to_x"]
    if promoted:
        lines.append("\nPROMOTED TO X (should have been tier 'high'):")
        for s in promoted[-3:]:
            lines.append(f'- "{s["title"]}" [{s.get("category", "other")}]')

    # Learned rules
    if rules:
        lines.append("\nEditor rules:")
        for r in rules[:10]:
            lines.append(f"- {r}")

    lines.append("\nWeight these preferences when deciding tier.")
    return "\n".join(lines)


def rank_article(
    title: str,
    snippet: str,
    score: int,
    score_breakdown: dict,
    feedback: dict | None = None,
) -> dict:
    """
    AI-powered ranking: determines tier and platform eligibility.

    Args:
        feedback: optional dict from state/feedback.json with user preference signals

    Returns:
        dict with keys: tier, reason, post_to_telegram, post_to_x, category
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        # Fallback: use score-based heuristics when no API key
        return _fallback_rank(score)

    try:
        from anthropic import Anthropic

        client = Anthropic(api_key=api_key)

        breakdown_str = ", ".join(f"{k}={v}" for k, v in score_breakdown.items() if v)
        prompt = RANKING_PROMPT.format(
            title=title or "(no title)",
            snippet=(snippet or "(no snippet)")[:500],
            score=score,
            score_breakdown=breakdown_str,
        )

        # Inject user feedback if available
        if feedback:
            feedback_section = _format_feedback_section(feedback)
            if feedback_section:
                prompt += feedback_section

        message = client.messages.create(
            model=RANKING_MODEL,
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}],
        )

        text = message.content[0].text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()

        result = json.loads(text)

        tier = str(result.get("tier", "low")).lower()
        if tier not in ("high", "medium", "low", "reject"):
            tier = "low"

        return {
            "tier": tier,
            "reason": str(result.get("reason", "")),
            "post_to_telegram": bool(result.get("post_to_telegram", tier != "reject")),
            "post_to_x": bool(result.get("post_to_x", tier == "high")),
            "category": str(result.get("category", "other")).lower(),
        }

    except json.JSONDecodeError as e:
        logger.warning(f"Ranking agent parse error: {e}")
        return _fallback_rank(score)

    except Exception as e:
        logger.error(f"Ranking agent failed: {e}")
        return _fallback_rank(score)


def _fallback_rank(score: int) -> dict:
    """Score-based fallback when AI is unavailable."""
    if score >= 75:
        return {
            "tier": "high",
            "reason": "high score (AI unavailable)",
            "post_to_telegram": True,
            "post_to_x": True,
            "category": "other",
        }
    elif score >= 50:
        return {
            "tier": "medium",
            "reason": "medium score (AI unavailable)",
            "post_to_telegram": True,
            "post_to_x": False,
            "category": "other",
        }
    elif score >= 35:
        return {
            "tier": "low",
            "reason": "low score (AI unavailable)",
            "post_to_telegram": True,
            "post_to_x": False,
            "category": "other",
        }
    else:
        return {
            "tier": "reject",
            "reason": "below threshold (AI unavailable)",
            "post_to_telegram": False,
            "post_to_x": False,
            "category": "other",
        }
