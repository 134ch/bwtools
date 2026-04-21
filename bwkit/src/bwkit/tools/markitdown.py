"""markitdown adapter — local files + HTTP(S) URLs → Markdown.

Heavy deps (`markitdown`) are imported lazily inside convert(). Importing
this module must succeed even when the [markitdown] extra is not installed.
"""

from __future__ import annotations

from bwkit.core.errors import MissingExtraError, ToolError
from bwkit.core.spec import ToolSpec


def convert(source: str, hint: str | None = None) -> dict:
    """Convert a local file OR an HTTP(S) URL to Markdown.

    Args:
        source: Local filesystem path, or an http/https/file URL. Windows
            paths like ``C:\\foo\\bar.html`` are treated as local paths
            (strict scheme detection, not "contains colon").
        hint: Optional extension / media hint such as ``".pdf"`` or
            ``"pdf"``. Useful when the source has no extension.

    Returns:
        ``{"title": str | None, "text": str}``.
    """
    try:
        from markitdown import MarkItDown  # type: ignore[import-not-found]
    except ImportError as e:
        raise MissingExtraError(
            extra="markitdown",
            install="pip install 'bwkit[markitdown]'",
        ) from e

    from urllib.parse import urlparse

    parsed = urlparse(source)
    scheme = parsed.scheme.lower()
    # Windows drive letters look like "c" in urlparse — reject anything beyond our allow-list.
    is_url = scheme in ("http", "https")
    is_file = scheme in ("", "file") or len(scheme) == 1  # c:\... is a local path on Windows

    md = MarkItDown()
    normalized_hint = _normalize_hint(hint)

    try:
        if is_url:
            res = md.convert_url(source, file_extension=normalized_hint)
        elif is_file:
            path = parsed.path if scheme == "file" else source
            res = md.convert_local(path, file_extension=normalized_hint)
        else:
            raise ToolError(code="unsupported_scheme", message=f"unsupported scheme: {scheme!r}")
    except (MissingExtraError, ToolError):
        raise
    except FileNotFoundError as e:
        raise ToolError(code="source_not_found", message=str(e)) from e
    except Exception as e:
        raise ToolError(code="conversion_failed", message=str(e)) from e

    return {"title": getattr(res, "title", None), "text": res.text_content}


def _normalize_hint(hint: str | None) -> str | None:
    if not hint:
        return None
    return hint if hint.startswith(".") else f".{hint}"


SPEC = ToolSpec(
    name="markitdown",
    summary="Convert local files or HTTP(S) URLs to Markdown (PDF, DOCX, PPTX, XLSX, HTML, text).",
    upstream="https://github.com/microsoft/markitdown",
    maintained=True,
    default_enabled=True,
    extras=("markitdown",),
    env_vars=(),
    run=convert,
)
