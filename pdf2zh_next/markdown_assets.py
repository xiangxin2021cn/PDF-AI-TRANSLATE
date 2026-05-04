from __future__ import annotations

import base64
import logging
import mimetypes
import re
import shutil
from pathlib import Path
from urllib.parse import unquote
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

MARKDOWN_IMAGE_RE = re.compile(r"(!\[[^\]]*\]\()([^)]*)(\))")
REMOTE_IMAGE_PREFIXES = ("http://", "https://")


def _unique_base_dirs(base_dirs) -> list[Path]:
    unique: list[Path] = []
    seen: set[str] = set()
    for base_dir in base_dirs or []:
        if base_dir in (None, ""):
            continue
        path = Path(base_dir)
        key = str(path.resolve()) if path.exists() else str(path.absolute())
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def _extract_destination_path(destination: str) -> str:
    value = (destination or "").strip()
    if not value:
        return ""
    if value.startswith("<"):
        end = value.find(">")
        if end > 0:
            return value[1:end].strip()
    return value.split(maxsplit=1)[0].strip()


def _is_embedded_or_remote(ref: str) -> bool:
    lower_ref = ref.lower()
    return lower_ref.startswith("data:") or lower_ref.startswith(REMOTE_IMAGE_PREFIXES)


def _clean_local_ref(ref: str) -> str:
    cleaned = unquote((ref or "").strip()).replace("\\", "/")
    if "#" in cleaned:
        cleaned = cleaned.split("#", 1)[0]
    if "?" in cleaned:
        cleaned = cleaned.split("?", 1)[0]
    return cleaned.strip()


def _candidate_relative_paths(ref: str) -> list[Path]:
    cleaned = _clean_local_ref(ref)
    if not cleaned:
        return []
    candidates = [Path(cleaned)]
    if cleaned.startswith("./"):
        candidates.append(Path(cleaned[2:]))
    name = Path(cleaned).name
    if name and Path(cleaned) != Path(name):
        candidates.append(Path(name))
    deduped: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.as_posix()
        if key not in seen:
            seen.add(key)
            deduped.append(candidate)
    return deduped


def resolve_markdown_image_path(ref: str, base_dirs) -> Path | None:
    ref = _extract_destination_path(ref)
    if not ref or _is_embedded_or_remote(ref):
        return None

    parsed = urlparse(ref)
    if parsed.scheme == "file":
        file_path = Path(unquote(parsed.path))
        return file_path if file_path.is_file() else None
    if parsed.scheme:
        return None

    cleaned = _clean_local_ref(ref)
    direct_path = Path(cleaned)
    if direct_path.is_absolute() and direct_path.is_file():
        return direct_path

    for base_dir in _unique_base_dirs(base_dirs):
        for relative_path in _candidate_relative_paths(cleaned):
            candidate = base_dir / relative_path
            if candidate.is_file():
                return candidate
    return None


def _target_relative_image_path(ref: str, target_prefix: str = "images") -> Path:
    cleaned = _clean_local_ref(_extract_destination_path(ref))
    relative_path = Path(cleaned)
    if relative_path.parts and relative_path.parts[0] == target_prefix:
        return relative_path
    name = relative_path.name or "image.png"
    return Path(target_prefix) / name


def copy_markdown_images_to_dir(
    markdown_content: str,
    *,
    source_base_dirs,
    target_base_dir: str | Path,
    target_prefix: str = "images",
) -> tuple[str, int]:
    target_base = Path(target_base_dir)
    copied = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal copied
        ref = _extract_destination_path(match.group(2))
        if not ref or _is_embedded_or_remote(ref):
            return match.group(0)

        source_path = resolve_markdown_image_path(ref, source_base_dirs)
        if not source_path:
            return match.group(0)

        target_relative = _target_relative_image_path(ref, target_prefix=target_prefix)
        target_path = target_base / target_relative
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if source_path.resolve() != target_path.resolve():
                shutil.copy2(source_path, target_path)
                copied += 1
        except Exception:
            logger.warning(
                "Failed to copy Markdown image %s", source_path, exc_info=True
            )
            return match.group(0)

        return f"{match.group(1)}{target_relative.as_posix()}{match.group(3)}"

    return MARKDOWN_IMAGE_RE.sub(replace, markdown_content or ""), copied


def embed_markdown_images_as_data_uris(markdown_content: str, *, base_dirs) -> str:
    def replace(match: re.Match[str]) -> str:
        ref = _extract_destination_path(match.group(2))
        if not ref or _is_embedded_or_remote(ref):
            return match.group(0)

        image_path = resolve_markdown_image_path(ref, base_dirs)
        if not image_path:
            return match.group(0)

        try:
            image_bytes = image_path.read_bytes()
        except Exception:
            logger.warning(
                "Failed to read Markdown image %s", image_path, exc_info=True
            )
            return match.group(0)

        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
        if not mime_type.startswith("image/"):
            mime_type = "image/png"
        encoded = base64.b64encode(image_bytes).decode("ascii")
        data_uri = f"data:{mime_type};base64,{encoded}"
        return f"{match.group(1)}{data_uri}{match.group(3)}"

    return MARKDOWN_IMAGE_RE.sub(replace, markdown_content or "")
