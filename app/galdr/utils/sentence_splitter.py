"""Async sentence splitter for the streaming TTS pipeline.

Buffers LLM token chunks and yields complete sentences so TTS can start
on the first sentence while the LLM continues generating the rest.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

# Match sentence-ending punctuation followed by whitespace.
# Negative lookbehind for '.' prevents splitting on ellipsis mid-word.
_SENT_END = re.compile(r'(?<=[!?])\s+|(?<=[^.][.])\s+')


async def split_sentences(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Buffer async token stream and yield complete sentences.

    Splits on [.!?] followed by whitespace. Handles ellipsis correctly —
    '...' mid-sentence does not trigger a split.
    """
    buf = ""
    async for chunk in tokens:
        buf += chunk
        while True:
            m = _SENT_END.search(buf)
            if not m:
                break
            sentence = buf[: m.start() + 1].strip()
            buf = buf[m.end() :]
            if sentence:
                yield sentence
    remainder = buf.strip()
    if remainder:
        yield remainder
