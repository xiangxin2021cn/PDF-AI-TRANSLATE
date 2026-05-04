"""Utilities for MinerU Markdown-style translation outputs.

This module keeps the scanned-PDF route structure-first: MinerU extracts
document blocks, translation happens on stable text units, and Markdown is
rendered after formulas, links, code spans, and other fragile fragments are
protected.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, Iterable


PLACEHOLDER_PREFIX = "ZXQKEEP"


@dataclass
class ProtectedFragment:
    placeholder: str
    value: str
    kind: str


@dataclass
class TranslationUnit:
    id: str
    page_num: int
    block_index: int
    kind: str
    source: str
    source_hash: str
    protected_source: str
    translated: str | None = None
    status: str = "pending"
    error: str | None = None
    protections: list[ProtectedFragment] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["protections"] = [asdict(item) for item in self.protections or []]
        return data


PROTECTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("display_math", r"\$\$.*?\$\$"),
    ("bracket_math", r"\\\[.*?\\\]"),
    ("paren_math", r"\\\(.*?\\\)"),
    ("inline_code", r"`[^`\n]+`"),
    ("inline_math", r"(?<!\$)\$(?!\$)(?:\\.|[^$\n])+\$(?!\$)"),
    ("image", r"!\[[^\]]*\]\([^\)]*\)"),
    ("link_target", r"(?<=\]\()[^\)]+(?=\))"),
    ("url", r"https?://[^\s)]+"),
    ("html_tag", r"</?[^>]+>"),
)


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def should_translate_text(text: str, min_length: int = 2) -> bool:
    stripped = text.strip()
    if len(stripped) < min_length:
        return False
    if not re.search(r"[^\W\d_]", stripped, re.UNICODE):
        return False
    if re.fullmatch(r"[\s\d\W_]+", stripped, re.UNICODE):
        return False
    return True


def protect_markdown_fragments(text: str) -> tuple[str, list[ProtectedFragment]]:
    protections: list[ProtectedFragment] = []
    protected = text
    placeholder_base = f"{PLACEHOLDER_PREFIX}{hash_text(text).upper()}"

    def make_replacer(kind: str) -> Callable[[re.Match[str]], str]:
        def replace(match: re.Match[str]) -> str:
            placeholder = f"{placeholder_base}{len(protections):04d}ZXQ"
            protections.append(
                ProtectedFragment(
                    placeholder=placeholder,
                    value=match.group(0),
                    kind=kind,
                )
            )
            return placeholder

        return replace

    for kind, pattern in PROTECTION_PATTERNS:
        protected = re.sub(pattern, make_replacer(kind), protected, flags=re.DOTALL)

    return protected, protections


def restore_markdown_fragments(text: str, protections: Iterable[ProtectedFragment]) -> str:
    restored = text
    for item in protections:
        restored = restored.replace(item.placeholder, item.value)
    return restored


def protect_translation_unit(
    unit_id: str,
    page_num: int,
    block_index: int,
    kind: str,
    source: str,
) -> TranslationUnit:
    protected_source, protections = protect_markdown_fragments(source)
    return TranslationUnit(
        id=unit_id,
        page_num=page_num,
        block_index=block_index,
        kind=kind,
        source=source,
        source_hash=hash_text(source),
        protected_source=protected_source,
        protections=protections,
    )


def translate_protected_text(
    text: str,
    translate_func: Callable[[str], str],
    min_length: int = 2,
) -> tuple[str, str, list[ProtectedFragment]]:
    if not should_translate_text(text, min_length=min_length):
        return text, "skipped", []

    protected_text, protections = protect_markdown_fragments(text)
    translated = translate_func(protected_text)
    return restore_markdown_fragments(translated, protections), "translated", protections


def build_translation_units(page_results: list[Any], min_length: int = 2) -> list[TranslationUnit]:
    units: list[TranslationUnit] = []
    for result in page_results:
        blocks = getattr(result, "translated_blocks", None) or getattr(result, "original_blocks", [])
        for block in blocks:
            source = getattr(block, "original", "") or ""
            if not should_translate_text(source, min_length=min_length):
                continue
            unit = protect_translation_unit(
                unit_id=getattr(block, "id", f"page_{result.page_num}_block_{len(units)}"),
                page_num=getattr(block, "page_num", result.page_num),
                block_index=getattr(block, "block_index", 0),
                kind=getattr(block, "type", "text"),
                source=source,
            )
            translated = getattr(block, "translated", None)
            if translated:
                unit.translated = translated
                unit.status = "translated"
            units.append(unit)
    return units


def build_translation_map(page_results: list[Any], min_length: int = 2) -> dict[str, Any]:
    units: list[dict[str, Any]] = []
    for result in page_results:
        for block in getattr(result, "translated_blocks", []):
            source = getattr(block, "original", "") or ""
            unit = protect_translation_unit(
                unit_id=getattr(block, "id", f"page_{result.page_num}_block_{len(units)}"),
                page_num=getattr(block, "page_num", result.page_num),
                block_index=getattr(block, "block_index", 0),
                kind=getattr(block, "type", "text"),
                source=source,
            )
            translated = getattr(block, "translated", None)
            unit.translated = translated
            unit.status = "translated" if translated and should_translate_text(source, min_length=min_length) else "skipped"
            units.append(unit.to_dict())

    return {
        "generated_at": datetime.now().isoformat(),
        "unit_count": len(units),
        "units": units,
    }


def translation_units_to_jsonl(units: list[TranslationUnit]) -> str:
    return "\n".join(json.dumps(unit.to_dict(), ensure_ascii=False) for unit in units)


def json_dumps_safe(data: Any) -> str:
    return json.dumps(to_json_safe(data), ensure_ascii=False, indent=2)


def to_json_safe(data: Any) -> Any:
    if isinstance(data, (bytes, bytearray)):
        return f"<binary:{len(data)} bytes>"
    if isinstance(data, dict):
        safe: dict[str, Any] = {}
        for key, value in data.items():
            if key == "image":
                safe[key] = "<image>"
            else:
                safe[str(key)] = to_json_safe(value)
        return safe
    if isinstance(data, (list, tuple)):
        return [to_json_safe(item) for item in data]
    if isinstance(data, (str, int, float, bool)) or data is None:
        return data
    if hasattr(data, "__array__"):
        shape = getattr(data, "shape", None)
        return f"<array shape={shape}>" if shape else "<array>"
    if hasattr(data, "isoformat"):
        try:
            return data.isoformat()
        except Exception:
            pass
    return str(data)


def build_raw_structure_payload(page_results: list[Any]) -> dict[str, Any]:
    return {
        "generated_at": datetime.now().isoformat(),
        "total_pages": len(page_results),
        "pages": [to_json_safe(getattr(result, "raw_structure", {})) for result in page_results],
    }


def build_source_markdown(page_results: list[Any]) -> str:
    lines: list[str] = ["# MinerU OCR Markdown", ""]

    for result in page_results:
        page_num = getattr(result, "page_num", 0)
        lines.append(f"## Page {page_num}")
        lines.append("")

        raw_structure = getattr(result, "raw_structure", {}) or {}
        for index, block in enumerate(raw_structure.get("blocks", [])):
            rendered = render_block_markdown(block, page_num, index)
            if rendered:
                lines.append(rendered)
                lines.append("")

    return "\n".join(lines).strip() + "\n"


def render_block_markdown(block: dict[str, Any], page_num: int, block_index: int) -> str:
    block_type = block.get("type", "text")
    content = (block.get("content") or "").strip()

    if block_type == "text":
        return content

    if block_type == "formula":
        latex = (block.get("latex") or content).strip()
        if not latex:
            return ""
        if block.get("inline"):
            if latex.startswith("$"):
                return latex
            return f"${latex}$"
        if latex.startswith("$$") or latex.startswith("\\["):
            return latex
        return f"$$\n{latex}\n$$"

    if block_type == "table":
        markdown = (block.get("markdown") or "").strip()
        if markdown:
            return markdown
        html = (block.get("html") or "").strip()
        if html:
            return html
        return content

    if block_type == "figure":
        caption = (block.get("caption") or content).strip()
        image_name = f"images/page_{page_num}_fig_{block_index}.png"
        alt_text = caption or "image"
        if caption:
            return f"![{alt_text}]({image_name})\n\n*{caption}*"
        return f"![{alt_text}]({image_name})"

    return content