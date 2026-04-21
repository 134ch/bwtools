from __future__ import annotations

import pytest

from bwkit.core.errors import ToolError
from bwkit.tools.markitdown import _normalize_hint, convert

pytest.importorskip("markitdown", reason="install bwkit[markitdown] to run this test")


def test_convert_local_html(bwkit_home, tmp_path):
    html = tmp_path / "doc.html"
    html.write_text("<html><head><title>Hello</title></head><body><h1>Heading</h1><p>Body.</p></body></html>", encoding="utf-8")
    out = convert(str(html))
    assert "text" in out and "title" in out
    assert "Heading" in out["text"] or "# Heading" in out["text"]


def test_windows_path_is_local_not_url(bwkit_home, tmp_path, monkeypatch):
    # We don't need an actual C:\ path to exist — we just want to prove that
    # a single-letter scheme (drive letter) routes through the local branch.
    # Sabotage convert_local so we can confirm which branch is taken.
    import bwkit.tools.markitdown as mk

    class Stub:
        def convert_local(self, path, file_extension=None):
            Stub.last = ("local", path, file_extension)
            class R:
                text_content = "OK"
                title = None
            return R()
        def convert_url(self, url, file_extension=None):
            raise AssertionError("should not take URL branch for Windows path")

    # Monkeypatch the MarkItDown constructor path to return our stub.
    monkeypatch.setattr(mk, "convert", mk.convert)  # no-op; kept for symmetry
    import markitdown as _md
    monkeypatch.setattr(_md, "MarkItDown", Stub)

    out = convert(r"C:\foo\bar.html")
    assert out == {"title": None, "text": "OK"}
    assert Stub.last[0] == "local"


def test_unsupported_scheme_classifies(bwkit_home):
    with pytest.raises(ToolError) as exc:
        convert("ftp://example.com/x.pdf")
    assert exc.value.code == "unsupported_scheme"


def test_source_not_found_classifies(bwkit_home, tmp_path):
    missing = tmp_path / "does_not_exist.pdf"
    with pytest.raises(ToolError) as exc:
        convert(str(missing))
    # markitdown may surface this as FileNotFoundError (→ source_not_found)
    # or a more generic failure (→ conversion_failed). Accept either.
    assert exc.value.code in ("source_not_found", "conversion_failed")


def test_normalize_hint():
    assert _normalize_hint(None) is None
    assert _normalize_hint("") is None
    assert _normalize_hint("pdf") == ".pdf"
    assert _normalize_hint(".pdf") == ".pdf"
