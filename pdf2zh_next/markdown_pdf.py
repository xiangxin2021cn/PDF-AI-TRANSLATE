"""Markdown to A4 PDF rendering utilities."""
from __future__ import annotations

import contextlib
import html
import logging
import tempfile
import uuid
from pathlib import Path

import fitz

from pdf2zh_next.markdown_preview import MarkdownPreview

logger = logging.getLogger(__name__)


def markdown_to_a4_pdf_bytes(
    markdown_content: str,
    *,
    title: str = "Translated Markdown",
    base_dir: str | Path | None = None,
) -> bytes:
    """Render Markdown content to a standard A4 PDF and return its bytes."""
    temp_path = Path(tempfile.gettempdir()) / f"pdf2zh_markdown_{uuid.uuid4().hex}.pdf"
    try:
        markdown_to_a4_pdf(
            markdown_content,
            temp_path,
            title=title,
            base_dir=base_dir,
        )
        return temp_path.read_bytes()
    finally:
        with contextlib.suppress(OSError):
            temp_path.unlink()


def markdown_to_a4_pdf(
    markdown_content: str,
    output_path: str | Path,
    *,
    title: str = "Translated Markdown",
    base_dir: str | Path | None = None,
) -> Path:
    """Render Markdown content to a standard A4 PDF file."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    body_html = MarkdownPreview._markdown_to_html(markdown_content or " ")
    document_html = f"""
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
</head>
<body>
<article class="markdown-body">
{body_html}
</article>
</body>
</html>
"""
    css = """
body {
    font-family: "Noto Sans CJK SC", "Microsoft YaHei", "PingFang SC", "Segoe UI", Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.56;
    color: #111827;
}
.markdown-body { width: 100%; }
h1, h2, h3, h4, h5, h6 {
    font-weight: 700;
    line-height: 1.24;
    margin: 0.85em 0 0.42em;
    page-break-after: avoid;
}
h1 { font-size: 20pt; border-bottom: 0.75pt solid #d1d5db; padding-bottom: 5pt; }
h2 { font-size: 15.5pt; border-bottom: 0.5pt solid #e5e7eb; padding-bottom: 3pt; }
h3 { font-size: 13pt; }
p { margin: 0 0 8pt; }
ul, ol { margin: 0 0 8pt 16pt; padding-left: 10pt; }
li { margin: 0 0 3pt; }
blockquote {
    margin: 8pt 0;
    padding: 2pt 0 2pt 10pt;
    border-left: 3pt solid #d1d5db;
    color: #4b5563;
}
pre {
    font-family: Consolas, "Courier New", monospace;
    font-size: 8.6pt;
    white-space: pre-wrap;
    background: #f3f4f6;
    border: 0.5pt solid #e5e7eb;
    padding: 7pt;
    margin: 7pt 0;
}
code {
    font-family: Consolas, "Courier New", monospace;
    font-size: 8.8pt;
    background: #f3f4f6;
    padding: 1pt 2pt;
}
table {
    border-collapse: collapse;
    width: 100%;
    margin: 7pt 0 10pt;
    page-break-inside: avoid;
}
th, td {
    border: 0.5pt solid #d1d5db;
    padding: 4pt 5pt;
    vertical-align: top;
    text-align: left;
}
th { background: #f3f4f6; font-weight: 700; }
img { max-width: 100%; height: auto; }
hr { border: 0; border-top: 0.75pt solid #e5e7eb; margin: 11pt 0; }
a { color: #1d4ed8; text-decoration: none; }
"""

    archive = None
    if base_dir is not None:
        with contextlib.suppress(Exception):
            archive = fitz.Archive(str(Path(base_dir)))

    writer = fitz.DocumentWriter(str(output_path))
    try:
        story = fitz.Story(document_html, user_css=css, archive=archive, em=12)
        mediabox = fitz.paper_rect("a4")
        margin = 54
        content_rect = fitz.Rect(
            margin,
            margin,
            mediabox.width - margin,
            mediabox.height - margin,
        )

        def rectfn(_rect_num, _filled):
            return mediabox, content_rect, fitz.Matrix(1, 0, 0, 1, 0, 0)

        story.write(writer, rectfn)
    finally:
        writer.close()

    logger.info("Markdown A4 PDF generated: %s", output_path)
    return output_path
