"""Async sentence splitter for the streaming TTS pipeline.

Buffers LLM token chunks and yields complete sentences so TTS can start
on the first sentence while the LLM continues generating the rest.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator

_SENT_END = re.compile(r'(?<=[!?])\s+|(?<=[^.][.])\s+')

# Strip markdown that TTS reads literally: **bold**, *italic*, __under__, `code`, # headings
_MD_NOISE = re.compile(r'\*{1,3}|_{1,2}|`|^#{1,6}\s*', re.MULTILINE)


def _clean(text: str) -> str:
    return _MD_NOISE.sub('', text).strip()


async def split_sentences(tokens: AsyncIterator[str]) -> AsyncIterator[str]:
    """Buffer async token stream and yield complete sentences.

    Splits on [.!?] followed by whitespace. Handles ellipsis correctly --
    '...' mid-sentence does not trigger a split.
    Strips markdown formatting before yielding so TTS never reads asterisks.
    """
    buf = ""
    async for chunk in tokens:
        buf += chunk
        while True:
            m = _SENT_END.search(buf)
            if not m:
                break
            sentence = _clean(buf[: m.start() + 1])
            buf = buf[m.end() :]
            if sentence:
                yield sentence
    remainder = _clean(buf)
    if remainder:
        yield remainder
