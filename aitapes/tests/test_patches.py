"""Tests for patch system (v8.0 — AST-driven splicer)."""

from aitapes.patches import (
    LookupPath,
    Patch,
    PatchResult,
    apply_patch,
    format_patches_as_text,
    parse_build_output,
)


def test_parse_build_output() -> None:
    raw = {
        "patches": [
            {
                "file": "test.py",
                "target_symbol": "my_module.hello",
                "search": "old code",
                "replace": "new code",
                "reasoning": "fix the bug",
            }
        ],
        "uncertainties": [
            {
                "claim": "uncertain about X",
                "confidence": 0.6,
                "evidence": "some evidence",
                "alternative": "maybe Y",
            }
        ],
        "assumptions_made": ["assumed Z"],
    }
    output = parse_build_output(raw)
    assert len(output.patches) == 1
    assert output.patches[0].file == "test.py"
    assert output.patches[0].target_symbol == "my_module.hello"
    assert len(output.uncertainties) == 1
    assert output.uncertainties[0].confidence == 0.6
    assert len(output.assumptions) == 1


def test_apply_patch_success() -> None:
    patch = Patch(file="test.py", search="hello", replace="world", target_symbol="greet")
    result = apply_patch("say hello friend", patch)
    assert result.applied is True
    assert result.error is None


def test_apply_patch_failure() -> None:
    patch = Patch(file="test.py", search="nonexistent", replace="new", target_symbol="missing")
    result = apply_patch("some content", patch)
    assert result.applied is False
    assert result.error is not None


def test_apply_patch_ast_lookup() -> None:
    """v8.0: AST splicer finds function by target_symbol."""
    source = "def foo():\n    return 1\n\ndef bar():\n    return 2\n"
    patch = Patch(file="test.py", search="return 1", replace="return 42", target_symbol="foo")
    result = apply_patch(source, patch)
    assert result.applied is True
    assert result.lookup_path == LookupPath.AST_NODE


def test_apply_patch_fallback_to_search() -> None:
    """v8.0: Falls back to exact search when AST lookup fails."""
    source = "x = 1\ny = 2\n"
    patch = Patch(file="test.py", search="x = 1", replace="x = 99", target_symbol="no_such_sym")
    result = apply_patch(source, patch)
    assert result.applied is True
    assert result.lookup_path == LookupPath.SEARCH_EXACT


def test_apply_patch_empty_search() -> None:
    patch = Patch(file="test.py", search="", replace="new", target_symbol="")
    result = apply_patch("content", patch)
    assert result.applied is False


def test_apply_patch_multi_match() -> None:
    patch = Patch(file="test.py", search="dup", replace="new", target_symbol="missing")
    result = apply_patch("dup dup dup", patch)
    assert result.applied is False
    assert result.error is not None


def test_format_patches() -> None:
    patches = [
        Patch(file="a.py", search="x", replace="y", target_symbol="fn", reasoning="fix"),
    ]
    text = format_patches_as_text(patches)
    assert "a.py" in text
    assert "fix" in text
    assert "fn" in text


def test_patch_result_has_lookup_path() -> None:
    """v8.0: PatchResult records which lookup strategy was used."""
    p = Patch(file="f.py", search="a", replace="b", target_symbol="s")
    r = PatchResult(patch=p, applied=False, lookup_path=LookupPath.FAILED)
    assert r.lookup_path == LookupPath.FAILED
