from deepscout_research.phases.text_utils import locate_quote_in_content, normalize_match_key


def test_locate_quote_exact_match() -> None:
    content = "NMC batteries offer higher energy density than LFP chemistry."
    snippet = "higher energy density than LFP"
    assert locate_quote_in_content(snippet, content) == snippet


def test_locate_quote_normalizes_whitespace() -> None:
    content = "NMC   batteries offer\nhigher energy density."
    snippet = "NMC batteries offer higher energy density."
    assert locate_quote_in_content(snippet, content) is not None


def test_locate_quote_missing_returns_none() -> None:
    assert locate_quote_in_content("totally unrelated claim", "some content") is None


def test_normalize_match_key_strips_punctuation() -> None:
    assert normalize_match_key("Hello, world!") == "hello world"
