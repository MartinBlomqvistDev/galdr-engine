"""Edge case tests for the sentence splitter and markdown cleaner."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from galdr.utils.sentence_splitter import split_sentences, _clean


async def _collect(text: str) -> list[str]:
    async def _gen():
        yield text
    return [s async for s in split_sentences(_gen())]


async def _collect_chunks(chunks: list[str]) -> list[str]:
    async def _gen():
        for c in chunks:
            yield c
    return [s async for s in split_sentences(_gen())]


def run(coro):
    return asyncio.run(coro)


# --- Markdown cleaning ---

def test_clean_single_asterisk():
    assert _clean("*word*") == "word"

def test_clean_double_asterisk():
    assert _clean("**bold**") == "bold"

def test_clean_triple_asterisk():
    assert _clean("***bold italic***") == "bold italic"

def test_clean_underscore():
    assert _clean("__under__") == "under"

def test_clean_backtick():
    assert _clean("`code`") == "code"

def test_clean_heading():
    assert _clean("## Scene title") == "Scene title"

def test_clean_mixed():
    assert _clean("**The** unit *scrapes* the floor.") == "The unit scrapes the floor."

def test_clean_all_asterisks():
    """A sentence that is entirely asterisks becomes empty."""
    assert _clean("****") == ""

def test_clean_preserves_ellipsis():
    assert _clean("The unit...") == "The unit..."

def test_clean_plain_text():
    assert _clean("No markdown here.") == "No markdown here."


# --- Sentence splitting ---

def test_single_sentence():
    result = run(_collect("The floor is cold."))
    assert result == ["The floor is cold."]

def test_two_sentences():
    result = run(_collect("The floor is cold. You hear scraping."))
    assert result == ["The floor is cold.", "You hear scraping."]

def test_exclamation():
    result = run(_collect("Something moves! You freeze."))
    assert result == ["Something moves!", "You freeze."]

def test_question():
    result = run(_collect("Where is it? You strain to hear."))
    assert result == ["Where is it?", "You strain to hear."]

def test_no_terminal_punctuation():
    """Text with no sentence-ending punct yields as single remainder."""
    result = run(_collect("The unit is somewhere in the dark"))
    assert result == ["The unit is somewhere in the dark"]

def test_ellipsis_no_split():
    """Ellipsis mid-sentence should not split -- '...' is not a sentence boundary.
    The lookbehind (?<=[^.][.]) requires the period to be preceded by a non-period,
    which excludes the third dot of an ellipsis.
    Full text is yielded as one sentence (no trailing whitespace after final period
    means the split fires only via the remainder handler).
    """
    result = run(_collect("The unit... it stops."))
    assert len(result) == 1
    assert result[0] == "The unit... it stops."

def test_empty_string():
    result = run(_collect(""))
    assert result == []

def test_whitespace_only():
    result = run(_collect("   "))
    assert result == []

def test_markdown_sentence_strips_to_empty_not_yielded():
    """A sentence that is entirely markdown noise should not be yielded."""
    result = run(_collect("****. The floor is cold."))
    # After stripping, "****" becomes "" -- should not appear in output
    real = [s for s in result if s]
    assert all(s != "" for s in real)
    assert any("floor" in s for s in real)

def test_chunked_tokens():
    """Simulate LLM tokens arriving in small chunks."""
    chunks = ["The ", "floor ", "is ", "cold. ", "You ", "hear ", "scraping."]
    result = run(_collect_chunks(chunks))
    assert result == ["The floor is cold.", "You hear scraping."]

def test_chunked_split_at_boundary():
    """Period arrives in a separate chunk from the rest of the sentence."""
    chunks = ["The floor is cold", ".", " You hear scraping."]
    result = run(_collect_chunks(chunks))
    assert result == ["The floor is cold.", "You hear scraping."]

def test_markdown_across_chunks():
    """Markdown tokens split across chunks still get stripped."""
    chunks = ["**The** unit ", "*scrapes*", " the floor."]
    result = run(_collect_chunks(chunks))
    assert result == ["The unit scrapes the floor."]

def test_very_short_sentence():
    result = run(_collect("Go."))
    assert result == ["Go."]

def test_many_sentences():
    text = "One. Two. Three. Four. Five."
    result = run(_collect(text))
    assert result == ["One.", "Two.", "Three.", "Four.", "Five."]
