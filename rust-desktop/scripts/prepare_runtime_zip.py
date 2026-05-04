from __future__ import annotations

import os
import sys
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_DIR = ROOT / "electron-app" / "python_portable"
TARGET_DIR = ROOT / "rust-desktop" / "src-tauri" / "resources"
TARGET_ZIP = TARGET_DIR / "python_portable.zip"
EXCLUDED_FILENAMES = {
    ".env",
    "config.toml",
    "config.v3.toml",
    "config.v3.temp.toml",
}
EXCLUDED_DIRNAMES = {
    ".cache",
    ".config",
    "output",
    "tmp",
}


def should_exclude(relative_path: Path) -> bool:
    parts = set(relative_path.parts)
    if parts & EXCLUDED_DIRNAMES:
        return True
    filename = relative_path.name.lower()
    if filename in EXCLUDED_FILENAMES:
        return True
    return filename.startswith("config.v") and filename.endswith(".toml")


def iter_files(root: Path):
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [
            name
            for name in dirnames
            if name != "__pycache__" and name not in EXCLUDED_DIRNAMES
        ]
        for filename in filenames:
            if filename.endswith((".pyc", ".pyo")):
                continue
            path = Path(current_root) / filename
            relative_path = path.relative_to(root)
            if should_exclude(relative_path):
                continue
            yield path, relative_path


def main() -> int:
    if not (RUNTIME_DIR / "python.exe").exists():
        print(f"Missing runtime: {RUNTIME_DIR}", file=sys.stderr)
        return 1

    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    temp_zip = TARGET_ZIP.with_suffix(".zip.tmp")
    if temp_zip.exists():
        temp_zip.unlink()

    file_count = 0
    total_bytes = 0
    with zipfile.ZipFile(
        temp_zip, "w", compression=zipfile.ZIP_STORED, allowZip64=True
    ) as archive:
        for path, relative_path in iter_files(RUNTIME_DIR):
            archive.write(path, relative_path.as_posix())
            file_count += 1
            total_bytes += path.stat().st_size
            if file_count % 1000 == 0:
                print(f"Packed {file_count} files...")

    if TARGET_ZIP.exists():
        TARGET_ZIP.unlink()
    temp_zip.replace(TARGET_ZIP)
    print(f"Runtime zip ready: {TARGET_ZIP}")
    print(f"Files: {file_count}")
    print(f"Uncompressed MB: {total_bytes / 1024 / 1024:.2f}")
    print(f"Zip MB: {TARGET_ZIP.stat().st_size / 1024 / 1024:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
