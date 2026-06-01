"""Tests for _frontmatter.py — minimal YAML frontmatter serializer/deserializer."""

from __future__ import annotations

import pytest

from core.ralph._frontmatter import FrontmatterError, dumps, safe_load

# ============================================================================
# dumps — serialization
# ============================================================================


class TestDumps:
    def test_string_value(self) -> None:
        result = dumps({"name": "hello"})
        assert "name: hello" in result

    def test_int_value(self) -> None:
        result = dumps({"count": 42})
        assert "count: 42" in result

    def test_bool_value(self) -> None:
        result = dumps({"enabled": True})
        assert "enabled: true" in result
        result = dumps({"enabled": False})
        assert "enabled: false" in result

    def test_empty_dict(self) -> None:
        result = dumps({})
        assert result == "\n"

    def test_empty_list_value(self) -> None:
        result = dumps({"items": []})
        assert "items: []" in result

    def test_list_with_items(self) -> None:
        result = dumps({"tags": ["a", "b", "c"]})
        assert "tags:" in result
        assert "- a" in result
        assert "- b" in result
        assert "- c" in result

    def test_nested_dict(self) -> None:
        result = dumps({"meta": {"key": "val", "num": 7}})
        assert "meta:" in result
        assert "  key: val" in result
        assert "  num: 7" in result

    def test_multiple_keys(self) -> None:
        result = dumps({"a": 1, "b": 2})
        assert "a: 1" in result
        assert "b: 2" in result

    def test_quote_if_needed(self) -> None:
        """Strings with colons, hashes, or leading quotes get quoted."""
        result = dumps({"url": "https://example.com"})
        assert "'https://example.com'" in result

    def test_empty_string_value_uses_quotes(self) -> None:
        result = dumps({"key": ""})
        assert 'key: ""' in result


# ============================================================================
# safe_load — parsing
# ============================================================================


class TestSafeLoad:
    def test_string_value(self) -> None:
        result = safe_load("name: hello")
        assert result == {"name": "hello"}

    def test_int_value(self) -> None:
        result = safe_load("count: 42")
        assert result == {"count": 42}

    def test_bool_true(self) -> None:
        result = safe_load("enabled: true")
        assert result == {"enabled": True}

    def test_bool_false(self) -> None:
        result = safe_load("enabled: false")
        assert result == {"enabled": False}

    def test_bool_variants(self) -> None:
        result = safe_load("a: yes\nb: no\nc: on\nd: off")
        assert result == {"a": True, "b": False, "c": True, "d": False}

    def test_empty_input(self) -> None:
        result = safe_load("")
        assert result == {}

    def test_whitespace_input(self) -> None:
        result = safe_load("   \n  \n")
        assert result == {}

    def test_list_value_explicit(self) -> None:
        result = safe_load("items: []")
        assert result == {"items": []}

    def test_list_with_items(self) -> None:
        text = """tags:
- python
- yaml
- test"""
        result = safe_load(text)
        assert result == {"tags": ["python", "yaml", "test"]}

    def test_list_with_int_items(self) -> None:
        text = """numbers:
- 1
- 2
- 3"""
        result = safe_load(text)
        assert result == {"numbers": [1, 2, 3]}

    def test_list_with_bool_items(self) -> None:
        text = """flags:
- true
- false"""
        result = safe_load(text)
        assert result == {"flags": [True, False]}

    def test_nested_dict(self) -> None:
        text = """meta:
  key: val
  num: 7"""
        result = safe_load(text)
        assert result == {"meta": {"key": "val", "num": 7}}

    def test_explicit_empty_dict(self) -> None:
        result = safe_load("items: {}")
        assert result == {"items": {}}

    def test_quoted_string_value(self) -> None:
        text = """url: 'https://example.com'"""
        result = safe_load(text)
        assert result == {"url": "https://example.com"}

    def test_double_quoted_string(self) -> None:
        result = safe_load('greeting: "hello world"')
        assert result == {"greeting": "hello world"}

    def test_escaped_single_quotes(self) -> None:
        text = """name: 'it''s fine'"""
        result = safe_load(text)
        assert result == {"name": "it's fine"}

    def test_multiple_keys(self) -> None:
        text = """a: 1
b: hello
c: true"""
        result = safe_load(text)
        assert result == {"a": 1, "b": "hello", "c": True}

    def test_skip_empty_lines(self) -> None:
        text = """a: 1

b: 2"""
        result = safe_load(text)
        assert result == {"a": 1, "b": 2}

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_empty_value_at_end(self) -> None:
        """key: with no value and nothing following."""
        result = safe_load("name:")
        assert result == {"name": ""}

    def test_empty_value_mid_document(self) -> None:
        """key: with empty value followed by another key."""
        text = """name:
role: developer"""
        result = safe_load(text)
        assert result == {"name": "", "role": "developer"}

    def test_empty_value_then_list(self) -> None:
        """key: with no inline value but list items follow."""
        text = """items:
- alpha
- beta"""
        result = safe_load(text)
        assert result == {"items": ["alpha", "beta"]}

    def test_empty_value_then_dict(self) -> None:
        """key: with no inline value but nested dict follows."""
        text = """meta:
  version: 2
  status: active"""
        result = safe_load(text)
        assert result == {"meta": {"version": 2, "status": "active"}}

    def test_mixed_content(self) -> None:
        """Dict with scalars, list, and nested dict."""
        text = """name: project
tags:
- core
- test
settings:
  timeout: 30
  retry: true"""
        result = safe_load(text)
        assert result == {
            "name": "project",
            "tags": ["core", "test"],
            "settings": {"timeout": 30, "retry": True},
        }

    def test_empty_list_mid_document(self) -> None:
        """Explicit empty list followed by another key."""
        text = """items: []
next: value"""
        result = safe_load(text)
        assert result == {"items": [], "next": "value"}

    def test_empty_dict_mid_document(self) -> None:
        """Explicit empty dict followed by another key."""
        text = """items: {}
next: value"""
        result = safe_load(text)
        assert result == {"items": {}, "next": "value"}

    # ------------------------------------------------------------------
    # Error cases
    # ------------------------------------------------------------------

    def test_malformed_line_raises(self) -> None:
        """Line without a colon raises FrontmatterError."""
        with pytest.raises(FrontmatterError, match="Expected key:value"):
            safe_load("no-colon-here")

    def test_malformed_line_in_middle(self) -> None:
        """Line without a colon mid-document raises FrontmatterError."""
        text = """a: 1
badline
b: 2"""
        with pytest.raises(FrontmatterError):
            safe_load(text)


# ============================================================================
# Round-trip: dumps(safe_load(dumps(data))) == dumps(data)
# ============================================================================


class TestRoundTrip:
    def test_strings(self) -> None:
        data = {"name": "hello"}
        assert dumps(safe_load(dumps(data))) == dumps(data)

    def test_ints(self) -> None:
        data = {"count": 42}
        assert dumps(safe_load(dumps(data))) == dumps(data)

    def test_bools(self) -> None:
        assert dumps(safe_load(dumps({"x": True}))) == dumps({"x": True})
        assert dumps(safe_load(dumps({"x": False}))) == dumps({"x": False})

    def test_list_of_strings(self) -> None:
        data = {"tags": ["a", "b", "c"]}
        assert dumps(safe_load(dumps(data))) == dumps(data)

    def test_list_of_ints(self) -> None:
        data = {"numbers": [1, 2, 3]}
        assert dumps(safe_load(dumps(data))) == dumps(data)

    def test_empty_list(self) -> None:
        data = {"items": []}
        assert dumps(safe_load(dumps(data))) == dumps(data)

    def test_nested_dict(self) -> None:
        data = {"meta": {"key": "val", "num": 7}}
        result = safe_load(dumps(data))
        # dict order shouldn't matter for equality
        assert result == data

    def test_empty_dict(self) -> None:
        data = {"items": {}}
        assert dumps(safe_load(dumps(data))) == dumps(data)

    def test_mixed_complex(self) -> None:
        data = {
            "name": "test",
            "version": 2,
            "enabled": True,
            "tags": ["core", "edge"],
            "config": {"timeout": 30, "retry": False},
            "notes": "",
        }
        result = safe_load(dumps(data))
        assert result == data

    def test_multiple_keys_preserved(self) -> None:
        data = {"z": 3, "a": 1, "m": 2}
        # dumps serializes in insertion order, safe_load preserves on re-parse
        rerun = safe_load(dumps(data))
        assert rerun == data
