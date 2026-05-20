"""Content filtering — two layers: prompt-level (pre-generation) and regex (post-generation).

Prompt instructions are probabilistic; the LLM can ignore them. Regex is
deterministic. Hard safety requirements need the deterministic layer.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Always blocked regardless of node configuration
GLOBAL_BLOCKED_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b(självmord|suicid)\b", re.IGNORECASE),
    re.compile(r"\b(våldtäkt|sexuellt?\s+övergrepp)\b", re.IGNORECASE),
    re.compile(r"\b(barnpornografi|pedofil)\b", re.IGNORECASE),
]

# In-world fallback lines used when content is blocked
FALLBACK_RESPONSES = [
    "The narrator pauses for a moment and finds another thread in the story...",
    "The wind shifts and carries your words away. Let's explore a different path.",
    "That question doesn't belong in this story. What do you want to do instead?",
]


class ContentFilter:
    """Filters AI-generated text before it reaches the player."""

    def __init__(self, forbidden_topics: list[str] | None = None):
        self.forbidden_topics = forbidden_topics or []
        self._topic_patterns: list[re.Pattern] = []
        for topic in self.forbidden_topics:
            try:
                self._topic_patterns.append(re.compile(rf"\b{re.escape(topic)}\b", re.IGNORECASE))
            except re.error:
                logger.warning(f"Invalid pattern for topic: {topic}")

    def check(self, text: str) -> "FilterResult":
        """Run all filter layers in order. Returns a FilterResult with the final text."""
        # Global hard blocks
        for pattern in GLOBAL_BLOCKED_PATTERNS:
            if pattern.search(text):
                logger.warning(f"Globally blocked content matched: {pattern.pattern}")
                return FilterResult(passed=False, reason="global_block", fallback=FALLBACK_RESPONSES[0])

        # Per-node soft blocks
        for pattern in self._topic_patterns:
            if pattern.search(text):
                logger.info(f"Node-blocked topic matched: {pattern.pattern}")
                return FilterResult(passed=False, reason="node_block", fallback=FALLBACK_RESPONSES[1])

        # Length cap — truncate rather than block
        word_count = len(text.split())
        if word_count > 500:
            logger.info(f"Response too long ({word_count} words), truncating")
            truncated = " ".join(text.split()[:300]) + "..."
            return FilterResult(passed=True, text=truncated, truncated=True)

        return FilterResult(passed=True, text=text)


class FilterResult:
    def __init__(
        self,
        passed: bool,
        text: str = "",
        reason: str = "",
        fallback: str = "",
        truncated: bool = False,
    ):
        self.passed = passed
        self.text = text if passed else fallback
        self.reason = reason
        self.fallback = fallback
        self.truncated = truncated
