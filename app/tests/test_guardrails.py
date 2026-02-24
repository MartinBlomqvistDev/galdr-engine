"""Tester för guardrails/content filter."""

from galdr.guardrails.filter import ContentFilter


def test_clean_text_passes():
    f = ContentFilter()
    result = f.check("Berättaren viskar: 'Följ mig genom skogen.'")
    assert result.passed is True
    assert result.text == "Berättaren viskar: 'Följ mig genom skogen.'"


def test_global_blocked():
    f = ContentFilter()
    result = f.check("Karaktären tänker på självmord.")
    assert result.passed is False
    assert result.text != ""  # Fallback-svar


def test_topic_blocked():
    f = ContentFilter(forbidden_topics=["politik", "religion"])
    result = f.check("Karaktären diskuterar politik med borgmästaren.")
    assert result.passed is False


def test_topic_not_blocked():
    f = ContentFilter(forbidden_topics=["politik"])
    result = f.check("Karaktären diskuterar vädret med borgmästaren.")
    assert result.passed is True


def test_truncation():
    f = ContentFilter()
    long_text = " ".join(["ord"] * 600)
    result = f.check(long_text)
    assert result.passed is True
    assert result.truncated is True
    assert len(result.text.split()) < 600
