from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any


class SmokeTranslator:
    name = "SmokeTranslator"

    def translate(self, text: str, *args: Any, **kwargs: Any) -> str:
        return f"[SMOKE_TRANSLATED] {text}"


def parse_pages(value: str | None) -> list[int] | None:
    if not value or value.lower() in {"all", "全部"}:
        return None

    pages: list[int] = []
    for chunk in value.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            start, end = chunk.split("-", 1)
            pages.extend(range(int(start), int(end) + 1))
        else:
            pages.append(int(chunk))
    return pages


def import_app_components():
    try:
        from pdf2zh_next.config import ConfigManager
        from pdf2zh_next.config.model import SettingsModel
        from pdf2zh_next.mineru_optimized_pipeline import MinerUOptimizedPipeline
        from pdf2zh_next.storage_manager import StorageManager

        return ConfigManager, SettingsModel, MinerUOptimizedPipeline, StorageManager
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "缺少运行应用所需依赖，先执行 `uv sync` 或在完整 pdf2zh_next 环境中运行。"
            f"\n原始错误: {exc}"
        ) from exc


def check_vllm_server(server_url: str) -> None:
    import requests

    health = requests.get(f"{server_url.rstrip('/')}/health", timeout=15)
    health.raise_for_status()

    models = requests.get(f"{server_url.rstrip('/')}/v1/models", timeout=15)
    models.raise_for_status()
    model_ids = [item.get("id") for item in models.json().get("data", [])]
    print(f"vLLM server ok: {server_url}; models={model_ids}")


async def run_pipeline(args: argparse.Namespace) -> int:
    ConfigManager, SettingsModel, MinerUOptimizedPipeline, StorageManager = import_app_components()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"PDF不存在: {pdf_path}", file=sys.stderr)
        return 2

    if args.backend == "http-client" and not args.skip_server_check:
        check_vllm_server(args.server_url)

    if args.use_config_translator:
        cli_env = ConfigManager().initialize_cli_config()
        settings = cli_env.to_settings_model()
        translator = None
    else:
        settings = SettingsModel()
        translator = SmokeTranslator()

    settings.storage_root = args.storage_root
    settings.translation.lang_in = args.lang_in
    settings.translation.lang_out = args.lang_out
    settings.translation.min_text_length = args.min_text_length
    settings.mineru.enabled = True
    settings.mineru.backend = args.backend
    settings.mineru.model_path = args.model_path
    settings.mineru.server_url = args.server_url if args.backend == "http-client" else None
    settings.mineru.dpi = args.dpi
    settings.mineru.timeout_seconds = args.mineru_timeout_seconds

    storage = StorageManager(settings.storage_root)
    project_id = storage.create_project(
        pdf_path,
        {
            "title": f"mineru-smoke-{pdf_path.stem}",
            "lang_in": settings.translation.lang_in,
            "lang_out": settings.translation.lang_out,
            "translation_path": "mineru",
            "output_formats": ["source.md", "translation_units.jsonl", "translation_map.json"],
            "smoke_test": True,
        },
    )

    pipeline = MinerUOptimizedPipeline(
        settings=settings,
        storage_manager=storage,
        project_id=project_id,
        translator=translator,
    )

    pages = parse_pages(args.pages)
    seen_error = False
    async for event in pipeline.process_pdf(pdf_path, pages=pages):
        stage = event.get("stage", "unknown")
        progress = event.get("progress", 0.0)
        message = event.get("message", "")
        print(f"[{stage}] {progress:.1%} {message}")
        if stage == "error":
            seen_error = True

    mineru_dir = storage.projects_dir / project_id / "mineru"
    required_files = [
        "source.md",
        "raw_structure.json",
        "translation_units.jsonl",
        "translation_map.json",
        "bilingual.md",
        "translated.md",
        "bilingual.html",
        "translated.html",
        "structured.json",
    ]
    missing = [name for name in required_files if not (mineru_dir / name).exists()]

    units_path = mineru_dir / "translation_units.jsonl"
    unit_count = 0
    if units_path.exists():
        unit_count = sum(1 for line in units_path.read_text(encoding="utf-8").splitlines() if line.strip())

    map_path = mineru_dir / "translation_map.json"
    map_unit_count = 0
    if map_path.exists():
        map_data = json.loads(map_path.read_text(encoding="utf-8"))
        map_unit_count = int(map_data.get("unit_count", 0))

    print("\nSmoke result")
    print(f"project_id={project_id}")
    print(f"project_dir={storage.projects_dir / project_id}")
    print(f"translation_units={unit_count}")
    print(f"translation_map_units={map_unit_count}")
    print(f"missing_files={missing}")

    if missing or seen_error:
        storage.update_project_status(project_id, "failed", missing_files=missing)
        return 1

    storage.update_project_status(project_id, "completed", translation_units=unit_count)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Smoke-test the MinerU optimized pipeline.")
    parser.add_argument("--pdf", default="test/file/translate.cli.plain.text.pdf")
    parser.add_argument("--pages", default="1", help="Page list/range, e.g. 1 or 1-2,5. Use all for full PDF.")
    parser.add_argument("--backend", choices=["http-client", "transformers"], default="http-client")
    parser.add_argument("--server-url", default="http://127.0.0.1:8000")
    parser.add_argument("--skip-server-check", action="store_true")
    parser.add_argument("--model-path", default="opendatalab/MinerU2.5-Pro-2604-1.2B")
    parser.add_argument("--dpi", type=int, default=260)
    parser.add_argument("--mineru-timeout-seconds", type=int, default=300)
    parser.add_argument("--lang-in", default="en")
    parser.add_argument("--lang-out", default="zh")
    parser.add_argument("--min-text-length", type=int, default=5)
    parser.add_argument("--storage-root", default="storage")
    parser.add_argument(
        "--use-config-translator",
        action="store_true",
        help="Use the configured real translator instead of the local smoke translator.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    raise SystemExit(main())