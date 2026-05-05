"""MinerU优化翻译管道 - 按页处理、段落级双语对照

核心优化:
1. 按页增量处理，避免长时间等待
2. 段落级双语对照，便于校对
3. 分层缓存机制，支持断点续传
4. 内存优化，避免OOM
"""

from __future__ import annotations

import asyncio
import contextlib
import html
import json
import logging
import os
import queue as thread_queue
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, AsyncGenerator, Callable
from dataclasses import dataclass, asdict
from datetime import datetime

from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.markdown_assets import copy_markdown_images_to_dir
from pdf2zh_next.markdown_assets import embed_markdown_images_as_data_uris
from pdf2zh_next.mineru_adapter_fixed import MinerUFixedAdapter
from pdf2zh_next.mineru_markdown_units import (
    build_raw_structure_payload,
    build_source_markdown,
    build_translation_map,
    build_translation_units,
    hash_text,
    json_dumps_safe,
    protect_markdown_fragments,
    restore_markdown_fragments,
    should_translate_text,
    to_json_safe,
    translation_units_to_jsonl,
)
from pdf2zh_next.markdown_pdf import markdown_to_a4_pdf_bytes
from pdf2zh_next.mineru_online_client import MinerUOnlineClient
from pdf2zh_next.mineru_online_client import MinerUOnlineResult
from pdf2zh_next.storage_manager import StorageManager
from pdf2zh_next.translator import get_translator

logger = logging.getLogger(__name__)

LOCAL_EXTRACTION_PROGRESS_START = 0.30
LOCAL_EXTRACTION_PROGRESS_END = 0.80
LOCAL_EXTRACTION_HEARTBEAT_SECONDS = 15.0
LOCAL_EXTRACTION_POLL_SECONDS = 1.0


@dataclass
class ParagraphBlock:
    """段落块 - 最小的翻译和对照单元"""

    id: str
    type: str  # 'text', 'caption', 'table_cell', 'formula_caption'
    original: str
    translated: Optional[str] = None
    bbox: List[float] = None
    page_num: int = 0
    block_index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ParagraphBlock":
        return cls(**data)


@dataclass
class PageResult:
    """页面处理结果"""

    page_num: int
    original_blocks: List[ParagraphBlock]
    translated_blocks: List[ParagraphBlock]
    raw_structure: Dict[str, Any]
    processed_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "page_num": self.page_num,
            "original_blocks": [block.to_dict() for block in self.original_blocks],
            "translated_blocks": [block.to_dict() for block in self.translated_blocks],
            "raw_structure": to_json_safe(self.raw_structure),
            "processed_at": self.processed_at.isoformat(),
        }


class MinerUOptimizedPipeline:
    """优化的MinerU翻译管道

    特点:
    1. 按页增量处理，实时反馈进度
    2. 段落级双语对照
    3. 分层缓存和断点续传
    4. 内存优化管理
    """

    def __init__(
        self,
        settings: SettingsModel,
        storage_manager: StorageManager,
        project_id: str,
        translator: Any | None = None,
    ):
        """初始化优化管道

        Args:
            settings: 应用配置
            storage_manager: 存储管理器
            project_id: 项目ID
        """
        self.settings = settings
        self.storage = storage_manager
        self.project_id = project_id

        # 翻译引擎；smoke/integration tests can inject a local translator.
        self.translator = translator or get_translator(settings)

        # MinerU适配器
        mineru_settings = getattr(settings, "mineru", None)
        model_path = mineru_settings
        if model_path and hasattr(model_path, "model_path"):
            model_path = model_path.model_path
        else:
            model_path = "opendatalab/MinerU2.5-Pro-2604-1.2B"

        self.mineru_backend = (
            getattr(mineru_settings, "backend", "transformers")
            if mineru_settings
            else "transformers"
        )
        self.mineru = MinerUFixedAdapter(
            model_path=model_path,
            backend=self.mineru_backend,
            server_url=getattr(mineru_settings, "server_url", None)
            if mineru_settings
            else None,
            dpi=getattr(mineru_settings, "dpi", 260) if mineru_settings else 260,
        )
        self.mineru_timeout_seconds = (
            getattr(mineru_settings, "timeout_seconds", 300) if mineru_settings else 300
        )

        # 项目状态管理
        self.project_dir = self.storage.projects_dir / project_id
        self.mineru_dir = self.project_dir / "mineru"
        self.mineru_dir.mkdir(parents=True, exist_ok=True)

        # 缓存文件路径
        self.structure_cache_file = self.mineru_dir / "structure_cache.json"
        self.translation_cache_file = self.mineru_dir / "translation_cache.json"
        self.page_results_dir = self.mineru_dir / "pages"
        self.page_results_dir.mkdir(exist_ok=True)

        logger.info(f"MinerU优化管道初始化完成，项目ID: {project_id}")

    async def process_pdf(
        self,
        pdf_path: str | Path,
        pages: Optional[List[int]] = None,
        page_range: Optional[str] = None,
        progress_callback: Optional[Callable] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """处理PDF文件，生成实时进度

        Args:
            pdf_path: PDF文件路径
            pages: 指定页码列表
            page_range: 页码范围字符串
            progress_callback: 进度回调函数

        Yields:
            进度事件
        """
        pdf_path = Path(pdf_path)

        try:
            if self._uses_online_mineru_api():
                async for event in self._process_pdf_with_online_api(
                    pdf_path,
                    page_range=page_range or getattr(self.settings.pdf, "pages", None),
                    progress_callback=progress_callback,
                ):
                    yield event
                return

            async for event in self._process_pdf_with_local_batch(
                pdf_path,
                pages=pages,
                page_range=page_range,
                progress_callback=progress_callback,
            ):
                yield event
            return

        except Exception as e:
            logger.error(f"PDF处理失败: {e}", exc_info=True)
            yield {
                "stage": "error",
                "progress": 0.0,
                "message": f"处理失败: {str(e)}",
            }

    def _uses_online_mineru_api(self) -> bool:
        return self.mineru_backend in {"online-api", "online-agent"}

    async def _process_pdf_with_local_batch(
        self,
        pdf_path: Path,
        pages: Optional[List[int]] = None,
        page_range: str | None = None,
        progress_callback: Optional[Callable] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        from .progress_tracker import AsyncProgressTracker, ProcessingStage

        page_numbers = self._resolve_pages(pdf_path, pages, page_range)
        total_pages = len(page_numbers)
        progress_tracker = AsyncProgressTracker(total_pages)
        if progress_callback:
            progress_tracker.add_progress_callback(progress_callback)

        await progress_tracker.start()

        try:
            progress_tracker.update_stage(
                ProcessingStage.INIT, "正在初始化本地 MinerU 引擎..."
            )
            yield await self._get_next_event(progress_tracker)

            self.mineru.initialize()

            cached_results = await self._load_cached_results(page_numbers)
            cached_results = {
                page: result
                for page, result in cached_results.items()
                if self._is_local_batch_page_result(result)
            }
            missing_pages = [
                page for page in page_numbers if page not in cached_results
            ]
            page_results_by_num: dict[int, PageResult] = dict(cached_results)

            if missing_pages:
                from .progress_tracker import ProgressEvent

                progress_tracker.update_stage(
                    ProcessingStage.EXTRACTION,
                    f"正在按页识别本地 MinerU 文档结构，共 {len(missing_pages)} 页...",
                    {
                        "total_pages": total_pages,
                        "pending_pages": len(missing_pages),
                        "cached_pages": len(cached_results),
                        "timeout_seconds": self._mineru_timeout_seconds(),
                    },
                )
                yield await self._get_next_event(progress_tracker)

                extraction_total = len(missing_pages)
                for extraction_index, page_num in enumerate(missing_pages, start=1):
                    page_started_at = time.monotonic()
                    completed_before_page = extraction_index - 1
                    progress_tracker.put_event(
                        ProgressEvent(
                            stage=ProcessingStage.EXTRACTION,
                            progress=self._local_extraction_progress(
                                completed_before_page, extraction_total
                            ),
                            message=(
                                f"正在识别第 {extraction_index}/{extraction_total} 个待处理页面 "
                                f"(PDF第 {page_num} 页)..."
                            ),
                            details={
                                "page_num": page_num,
                                "current_page": extraction_index,
                                "total_pages": extraction_total,
                                "cached_pages": len(cached_results),
                                "completed_pages": completed_before_page,
                                "timeout_seconds": self._mineru_timeout_seconds(),
                                "status": "running",
                            },
                            page_num=page_num,
                            total_pages=total_pages,
                        )
                    )
                    yield await self._get_next_event(progress_tracker)

                    extract_task = asyncio.create_task(
                        self._run_mineru_call(
                            self.mineru.extract_single_page,
                            pdf_path,
                            page_num,
                        )
                    )
                    next_heartbeat_at = LOCAL_EXTRACTION_HEARTBEAT_SECONDS
                    while not extract_task.done():
                        elapsed = time.monotonic() - page_started_at
                        if elapsed >= next_heartbeat_at:
                            progress_tracker.put_event(
                                ProgressEvent(
                                    stage=ProcessingStage.EXTRACTION,
                                    progress=self._local_extraction_progress(
                                        completed_before_page, extraction_total
                                    ),
                                    message=(
                                        f"本地 MinerU 仍在识别 PDF 第 {page_num} 页，"
                                        f"已运行 {int(elapsed)} 秒..."
                                    ),
                                    details={
                                        "page_num": page_num,
                                        "current_page": extraction_index,
                                        "total_pages": extraction_total,
                                        "cached_pages": len(cached_results),
                                        "completed_pages": completed_before_page,
                                        "elapsed_seconds": round(elapsed, 1),
                                        "timeout_seconds": self._mineru_timeout_seconds(),
                                        "status": "running",
                                    },
                                    page_num=page_num,
                                    total_pages=total_pages,
                                )
                            )
                            next_heartbeat_at += LOCAL_EXTRACTION_HEARTBEAT_SECONDS
                        yield await self._get_next_event(progress_tracker)
                        await asyncio.sleep(LOCAL_EXTRACTION_POLL_SECONDS)

                    try:
                        page_structure = await extract_task
                    except Exception as e:
                        logger.error(
                            "本地 MinerU 识别第 %s 页失败: %s",
                            page_num,
                            e,
                            exc_info=True,
                        )
                        raise RuntimeError(
                            f"本地 MinerU 识别第 {page_num} 页失败: {e}"
                        ) from e

                    page_result = self._build_page_result_from_local_page(
                        page_structure,
                        pdf_path,
                        total_pages=total_pages,
                    )
                    page_results_by_num[page_num] = page_result
                    await self._save_page_result(page_result)

                    elapsed = time.monotonic() - page_started_at
                    progress_tracker.put_event(
                        ProgressEvent(
                            stage=ProcessingStage.EXTRACTION,
                            progress=self._local_extraction_progress(
                                extraction_index, extraction_total
                            ),
                            message=(
                                f"PDF 第 {page_num} 页识别完成 "
                                f"({extraction_index}/{extraction_total})"
                            ),
                            details={
                                "page_num": page_num,
                                "current_page": extraction_index,
                                "total_pages": extraction_total,
                                "cached_pages": len(cached_results),
                                "completed_pages": extraction_index,
                                "elapsed_seconds": round(elapsed, 1),
                                "blocks_found": len(page_result.original_blocks),
                                "status": "completed",
                            },
                            page_num=page_num,
                            total_pages=total_pages,
                        )
                    )
                    yield await self._get_next_event(progress_tracker)

            all_results = [
                page_results_by_num[page]
                for page in page_numbers
                if page in page_results_by_num
            ]
            if not all_results:
                raise RuntimeError("本地 MinerU 未返回可翻译的页面结构")

            untranslated_results = [
                result
                for result in all_results
                if result.page_num in missing_pages or not result.translated_blocks
            ]
            original_blocks: list[ParagraphBlock] = []
            for result in untranslated_results:
                original_blocks.extend(result.original_blocks)

            if original_blocks:
                progress_tracker.update_stage(
                    ProcessingStage.TRANSLATION,
                    f"正在统一翻译本地 MinerU 结构化文档的 {len(original_blocks)} 个内容单元...",
                )
                yield await self._get_next_event(progress_tracker)

                translation_task = asyncio.create_task(
                    self._translate_paragraphs(
                        original_blocks,
                        progress_tracker=progress_tracker,
                    )
                )
                while not translation_task.done():
                    yield await self._get_next_event(progress_tracker)
                    await asyncio.sleep(0.2)

                translated_blocks = await translation_task
                offset = 0
                for page_result in untranslated_results:
                    count = len(page_result.original_blocks)
                    page_result.translated_blocks = translated_blocks[
                        offset : offset + count
                    ]
                    offset += count

            progress_tracker.update_stage(
                ProcessingStage.FORMATTING,
                "正在生成 Markdown/HTML/A4 PDF/JSON 结果...",
            )
            yield await self._get_next_event(progress_tracker)

            for page_result in all_results:
                await self._save_page_result(page_result)
            await self._generate_outputs(all_results)

            for page_result in all_results:
                progress_tracker.mark_page_completed(page_result.page_num, 0)
            progress_tracker.complete("本地 MinerU 翻译完成")
            yield await self._get_next_event(progress_tracker)

        except Exception as e:
            logger.error("本地 MinerU 批处理失败: %s", e, exc_info=True)
            progress_tracker.error(f"处理失败: {str(e)}")
            yield await self._get_next_event(progress_tracker)
        finally:
            await progress_tracker.stop()

    def _build_page_results_from_local_document(
        self,
        local_result: dict[str, Any],
        pdf_path: Path,
    ) -> list[PageResult]:
        result_pages = (
            local_result.get("pages", []) if isinstance(local_result, dict) else []
        )
        page_results: list[PageResult] = []

        for fallback_index, page_structure in enumerate(result_pages, start=1):
            if not isinstance(page_structure, dict):
                continue
            page_num = page_structure.get("page_num") or fallback_index
            try:
                page_num = int(page_num)
            except (TypeError, ValueError):
                page_num = fallback_index

            raw_structure = dict(page_structure)
            raw_structure.setdefault("page_num", page_num)
            raw_structure.setdefault("source", str(pdf_path))
            raw_structure["mineru_local"] = {
                "backend": self.mineru_backend,
                "translation_flow": "document_batch_v1",
                "source": local_result.get("source")
                if isinstance(local_result, dict)
                else str(pdf_path),
                "total_pages": local_result.get("total_pages")
                if isinstance(local_result, dict)
                else len(result_pages),
            }
            original_blocks = self._extract_paragraph_blocks(raw_structure, page_num)
            page_results.append(
                PageResult(
                    page_num=page_num,
                    original_blocks=original_blocks,
                    translated_blocks=[],
                    raw_structure=raw_structure,
                    processed_at=datetime.now(),
                )
            )

        page_results.sort(key=lambda item: item.page_num)
        return page_results

    def _is_local_batch_page_result(self, result: PageResult) -> bool:
        raw_structure = result.raw_structure or {}
        mineru_local = raw_structure.get("mineru_local") or {}
        return mineru_local.get("translation_flow") == "document_batch_v1"

    async def _process_pdf_with_online_api(
        self,
        pdf_path: Path,
        page_range: str | None = None,
        progress_callback: Optional[Callable] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        from .progress_tracker import AsyncProgressTracker, ProcessingStage

        progress_tracker = AsyncProgressTracker(1)
        if progress_callback:
            progress_tracker.add_progress_callback(progress_callback)

        await progress_tracker.start()

        try:
            progress_tracker.update_stage(
                ProcessingStage.INIT, "正在初始化 MinerU 在线 API..."
            )
            yield await self._get_next_event(progress_tracker)

            extract_task = asyncio.create_task(
                self._extract_with_online_api(
                    pdf_path,
                    page_range=page_range,
                    progress_tracker=progress_tracker,
                )
            )

            while not extract_task.done():
                yield await self._get_next_event(progress_tracker)
                await asyncio.sleep(0.2)

            online_result = await extract_task
            yield await self._get_next_event(progress_tracker)

            page_results = self._build_page_results_from_online_result(
                online_result,
                pdf_path,
            )
            for page_result in page_results:
                await self._save_page_result(page_result)

            original_blocks: list[ParagraphBlock] = []
            for page_result in page_results:
                original_blocks.extend(page_result.original_blocks)

            progress_tracker.update_stage(
                ProcessingStage.TRANSLATION,
                f"正在翻译 MinerU 结构化文档的 {len(original_blocks)} 个内容单元...",
            )
            yield await self._get_next_event(progress_tracker)

            translation_task = asyncio.create_task(
                self._translate_paragraphs(
                    original_blocks,
                    progress_tracker=progress_tracker,
                )
            )
            while not translation_task.done():
                yield await self._get_next_event(progress_tracker)
                await asyncio.sleep(0.2)

            translated_blocks = await translation_task
            yield await self._get_next_event(progress_tracker)

            offset = 0
            for page_result in page_results:
                count = len(page_result.original_blocks)
                page_result.translated_blocks = translated_blocks[
                    offset : offset + count
                ]
                offset += count
                await self._save_page_result(page_result)

            progress_tracker.update_stage(
                ProcessingStage.FORMATTING, "正在生成 Markdown/HTML/A4 PDF/JSON 结果..."
            )
            yield await self._get_next_event(progress_tracker)

            await self._generate_outputs(page_results)
            for page_result in page_results:
                progress_tracker.mark_page_completed(page_result.page_num, 0)
            progress_tracker.complete("MinerU 在线 API 翻译完成")
            yield await self._get_next_event(progress_tracker)
            await progress_tracker.stop()

        except Exception as e:
            logger.error(f"MinerU online API processing failed: {e}", exc_info=True)
            progress_tracker.error(f"处理失败: {str(e)}")
            yield await self._get_next_event(progress_tracker)
            await progress_tracker.stop()

    async def _extract_with_online_api(
        self,
        pdf_path: Path,
        page_range: str | None,
        progress_tracker,
    ) -> MinerUOnlineResult:
        from .progress_tracker import ProgressEvent, ProcessingStage

        mineru_settings = getattr(self.settings, "mineru", None)
        client = MinerUOnlineClient(
            base_url=getattr(mineru_settings, "api_base_url", "https://mineru.net"),
            mode=self.mineru_backend,
            token=getattr(mineru_settings, "api_token", None),
            model_version=getattr(mineru_settings, "api_model_version", "vlm"),
            language=getattr(mineru_settings, "api_language", "ch"),
            is_ocr=getattr(mineru_settings, "api_is_ocr", True),
            enable_formula=getattr(mineru_settings, "api_enable_formula", True),
            enable_table=getattr(mineru_settings, "api_enable_table", True),
            timeout_seconds=getattr(mineru_settings, "timeout_seconds", 600),
            poll_interval_seconds=getattr(
                mineru_settings, "api_poll_interval_seconds", 3
            ),
            no_cache=getattr(mineru_settings, "api_no_cache", False),
            cache_tolerance=getattr(mineru_settings, "api_cache_tolerance", 900),
        )

        events: thread_queue.Queue[dict[str, Any]] = thread_queue.Queue()

        def report(
            progress: float, message: str, details: dict[str, Any] | None
        ) -> None:
            events.put(
                {
                    "progress": max(0.01, min(progress, 0.85)),
                    "message": message,
                    "details": details or {},
                }
            )

        task = asyncio.create_task(
            asyncio.to_thread(
                client.extract_file,
                pdf_path,
                page_range=page_range,
                artifact_dir=self.mineru_dir / "online_api",
                progress_callback=report,
            )
        )

        while not task.done():
            while True:
                try:
                    event = events.get_nowait()
                except thread_queue.Empty:
                    break
                progress_tracker.put_event(
                    ProgressEvent(
                        stage=ProcessingStage.EXTRACTION,
                        progress=event["progress"],
                        message=event["message"],
                        details=event["details"],
                        total_pages=1,
                    )
                )
            await asyncio.sleep(0.2)

        while True:
            try:
                event = events.get_nowait()
            except thread_queue.Empty:
                break
            progress_tracker.put_event(
                ProgressEvent(
                    stage=ProcessingStage.EXTRACTION,
                    progress=event["progress"],
                    message=event["message"],
                    details=event["details"],
                    total_pages=1,
                )
            )

        result = await task
        progress_tracker.put_event(
            ProgressEvent(
                stage=ProcessingStage.EXTRACTION,
                progress=0.85,
                message="MinerU 在线 API 已返回 Markdown 结构",
                total_pages=1,
            )
        )
        return result

    def _build_page_result_from_online_markdown(
        self,
        online_result: MinerUOnlineResult,
        pdf_path: Path,
    ) -> PageResult:
        raw_blocks = self._split_markdown_to_blocks(online_result.markdown)
        raw_structure = {
            "page_num": 1,
            "source": str(pdf_path),
            "blocks": raw_blocks,
            "mineru_online": {
                "backend": online_result.backend,
                "artifacts": online_result.artifacts,
                "payload": online_result.raw_payload,
            },
        }

        original_blocks: list[ParagraphBlock] = []
        min_length = getattr(self.settings.translation, "min_text_length", 5)
        for index, block in enumerate(raw_blocks):
            source = (block.get("markdown") or block.get("content") or "").strip()
            if not should_translate_text(source, min_length=min_length):
                continue
            original_blocks.append(
                ParagraphBlock(
                    id=f"online_page_1_block_{index}",
                    type="table_cell" if block.get("type") == "table" else "text",
                    original=source,
                    bbox=[],
                    page_num=1,
                    block_index=index,
                )
            )

        return PageResult(
            page_num=1,
            original_blocks=original_blocks,
            translated_blocks=[],
            raw_structure=raw_structure,
            processed_at=datetime.now(),
        )

    def _build_page_results_from_online_result(
        self,
        online_result: MinerUOnlineResult,
        pdf_path: Path,
    ) -> list[PageResult]:
        content_list_path = self._find_content_list_v2_path(online_result)
        if not content_list_path:
            logger.info(
                "MinerU content_list_v2.json not found; using Markdown fallback"
            )
            return [
                self._build_page_result_from_online_markdown(online_result, pdf_path)
            ]

        try:
            content_list = json.loads(content_list_path.read_text(encoding="utf-8"))
            page_results = self._build_page_results_from_content_list_v2(
                content_list,
                online_result,
                pdf_path,
                content_list_path,
            )
        except Exception as e:
            logger.warning(
                "Failed to build structured MinerU result from content_list_v2.json: %s; using Markdown fallback",
                e,
                exc_info=True,
            )
            return [
                self._build_page_result_from_online_markdown(online_result, pdf_path)
            ]

        if not page_results:
            logger.info(
                "MinerU content_list_v2.json produced no blocks; using Markdown fallback"
            )
            return [
                self._build_page_result_from_online_markdown(online_result, pdf_path)
            ]
        logger.info(
            "MinerU content_list_v2 parsed: pages=%s blocks=%s",
            len(page_results),
            sum(len(page.original_blocks) for page in page_results),
        )
        return page_results

    def _build_page_result_from_local_page(
        self,
        page_structure: dict[str, Any],
        pdf_path: Path,
        total_pages: int,
    ) -> PageResult:
        page_num = 0
        if isinstance(page_structure, dict):
            try:
                page_num = int(page_structure.get("page_num") or 0)
            except (TypeError, ValueError):
                page_num = 0

        local_result = {
            "source": str(pdf_path),
            "total_pages": total_pages,
            "pages": [page_structure if isinstance(page_structure, dict) else {}],
        }
        page_results = self._build_page_results_from_local_document(
            local_result,
            pdf_path,
        )
        if page_results:
            return page_results[0]

        return PageResult(
            page_num=page_num,
            original_blocks=[],
            translated_blocks=[],
            raw_structure={
                "page_num": page_num,
                "source": str(pdf_path),
                "blocks": [],
                "mineru_local": {
                    "backend": self.mineru_backend,
                    "translation_flow": "document_batch_v1",
                    "source": str(pdf_path),
                    "total_pages": total_pages,
                },
            },
            processed_at=datetime.now(),
        )

    def _find_content_list_v2_path(
        self, online_result: MinerUOnlineResult
    ) -> Path | None:
        artifacts = online_result.artifacts or {}
        candidates: list[Path] = []
        extract_dir = artifacts.get("extract_dir")
        if extract_dir:
            candidates.append(Path(extract_dir) / "content_list_v2.json")
        markdown_path = artifacts.get("markdown")
        if markdown_path:
            candidates.append(Path(markdown_path).parent / "content_list_v2.json")
        candidates.append(
            self.mineru_dir / "online_api" / "precise_extract" / "content_list_v2.json"
        )

        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _build_page_results_from_content_list_v2(
        self,
        content_list: Any,
        online_result: MinerUOnlineResult,
        pdf_path: Path,
        content_list_path: Path,
    ) -> list[PageResult]:
        pages = content_list if isinstance(content_list, list) else []
        page_results: list[PageResult] = []

        for page_index, page_items in enumerate(pages, start=1):
            if not isinstance(page_items, list):
                continue

            raw_blocks: list[dict[str, Any]] = []
            original_blocks: list[ParagraphBlock] = []
            for item_index, item in enumerate(page_items):
                if not isinstance(item, dict):
                    continue
                block = self._convert_content_list_item_to_block(
                    item,
                    page_num=page_index,
                    block_index=item_index,
                )
                if not block:
                    continue
                raw_blocks.append(block)
                source = (
                    block.get("markdown")
                    or block.get("html")
                    or block.get("content")
                    or ""
                ).strip()
                if not source:
                    continue
                original_blocks.append(
                    ParagraphBlock(
                        id=f"online_page_{page_index}_block_{item_index}",
                        type=block.get("type", "paragraph"),
                        original=source,
                        bbox=block.get("bbox", []),
                        page_num=page_index,
                        block_index=item_index,
                    )
                )

            if not raw_blocks and not original_blocks:
                continue
            raw_structure = {
                "page_num": page_index,
                "source": str(pdf_path),
                "blocks": raw_blocks,
                "mineru_online": {
                    "backend": online_result.backend,
                    "artifacts": online_result.artifacts,
                    "content_list_v2": str(content_list_path),
                    "payload": online_result.raw_payload,
                },
            }
            page_results.append(
                PageResult(
                    page_num=page_index,
                    original_blocks=original_blocks,
                    translated_blocks=[],
                    raw_structure=raw_structure,
                    processed_at=datetime.now(),
                )
            )

        return page_results

    def _convert_content_list_item_to_block(
        self,
        item: dict[str, Any],
        *,
        page_num: int,
        block_index: int,
    ) -> dict[str, Any] | None:
        source_type = str(item.get("type") or "paragraph")
        content = item.get("content") or {}
        bbox = item.get("bbox") or []
        block_id = f"page_{page_num}_item_{block_index}"

        if source_type == "title":
            level = (
                self._safe_heading_level(content.get("level", 1))
                if isinstance(content, dict)
                else 1
            )
            text = self._content_nodes_to_text(
                content.get("title_content", [])
                if isinstance(content, dict)
                else content
            )
            markdown = f"{'#' * level} {text}".strip() if text else ""
            return {
                "id": block_id,
                "type": "heading",
                "source_type": source_type,
                "level": level,
                "content": markdown,
                "markdown": markdown,
                "bbox": bbox,
            }

        if source_type == "table":
            table_html = ""
            if isinstance(content, dict):
                table_html = str(content.get("html") or "").strip()
            if not table_html:
                table_html = self._content_nodes_to_text(content)
            return {
                "id": block_id,
                "type": "html_table",
                "source_type": source_type,
                "content": table_html,
                "html": table_html,
                "bbox": bbox,
            }

        if source_type == "image":
            image_path = self._extract_image_path(content)
            caption = ""
            if isinstance(content, dict):
                caption = self._content_nodes_to_text(content.get("image_caption", []))
            markdown = f"![]({image_path})" if image_path else ""
            if caption:
                markdown = f"{markdown}\n\n*{caption}*" if markdown else f"*{caption}*"
            return {
                "id": block_id,
                "type": "image",
                "source_type": source_type,
                "content": markdown,
                "markdown": markdown,
                "image_path": image_path,
                "caption": caption,
                "bbox": bbox,
            }

        if source_type == "list":
            markdown = self._render_list_content(content)
            return {
                "id": block_id,
                "type": "paragraph",
                "source_type": source_type,
                "content": markdown,
                "markdown": markdown,
                "bbox": bbox,
            }

        if source_type in {"code", "formula", "equation", "equation_inline"}:
            text = self._content_nodes_to_text(content)
            block_type = "code" if source_type == "code" else "formula"
            return {
                "id": block_id,
                "type": block_type,
                "source_type": source_type,
                "content": text,
                "markdown": text,
                "bbox": bbox,
            }

        text = self._content_nodes_to_text(content)
        block_type = "paragraph"
        return {
            "id": block_id,
            "type": block_type,
            "source_type": source_type,
            "content": text,
            "markdown": text,
            "bbox": bbox,
        }

    def _safe_heading_level(self, value: Any) -> int:
        try:
            level = int(value)
        except (TypeError, ValueError):
            level = 1
        return max(1, min(level, 6))

    def _content_nodes_to_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, list):
            parts = [self._content_nodes_to_text(item) for item in value]
            return " ".join(part for part in parts if part).strip()
        if not isinstance(value, dict):
            return str(value).strip()

        node_type = value.get("type")
        content = value.get("content")
        if isinstance(content, str):
            text = content.strip()
            if (
                node_type in {"equation_inline", "equation"}
                and text
                and not text.startswith("$")
            ):
                return f"${text}$"
            return text

        known_keys = (
            "title_content",
            "paragraph_content",
            "item_content",
            "page_header_content",
            "page_footer_content",
            "page_number_content",
            "image_caption",
            "table_caption",
        )
        for key in known_keys:
            if key in value:
                return self._content_nodes_to_text(value.get(key))
        return ""

    def _render_list_content(self, content: Any) -> str:
        if not isinstance(content, dict):
            return self._content_nodes_to_text(content)
        list_items = content.get("list_items") or []
        ordered = str(content.get("list_type") or "").lower().startswith("ordered")
        lines: list[str] = []
        for index, item in enumerate(list_items, start=1):
            text = self._content_nodes_to_text(
                item.get("item_content", item) if isinstance(item, dict) else item
            )
            if not text:
                continue
            prefix = f"{index}." if ordered else "-"
            lines.append(f"{prefix} {text}")
        return "\n".join(lines)

    def _extract_image_path(self, content: Any) -> str:
        if not isinstance(content, dict):
            return ""
        image_source = content.get("image_source") or {}
        if not isinstance(image_source, dict):
            return ""
        path = str(
            image_source.get("path") or image_source.get("img_path") or ""
        ).strip()
        if path and not path.startswith(
            ("images/", "./", "../", "http://", "https://")
        ):
            path = f"images/{path}"
        return path

    def _split_markdown_to_blocks(self, markdown: str) -> list[dict[str, Any]]:
        blocks: list[dict[str, Any]] = []
        current: list[str] = []
        in_fence = False

        def flush() -> None:
            nonlocal current
            text = "\n".join(current).strip()
            current = []
            if not text:
                return
            if self._looks_like_markdown_table(text):
                blocks.append({"type": "table", "markdown": text, "content": text})
            else:
                blocks.append({"type": "text", "content": text})

        for line in markdown.replace("\r\n", "\n").split("\n"):
            stripped = line.strip()
            if stripped.startswith("```"):
                current.append(line)
                in_fence = not in_fence
                continue
            if in_fence:
                current.append(line)
                continue
            if not stripped:
                flush()
                continue
            if (
                stripped.startswith("|")
                and current
                and not current[0].strip().startswith("|")
            ):
                flush()
            elif (
                not stripped.startswith("|")
                and current
                and current[0].strip().startswith("|")
            ):
                flush()
            current.append(line)

        flush()
        return blocks

    def _looks_like_markdown_table(self, text: str) -> bool:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if len(lines) < 2:
            return False
        if not all(line.startswith("|") and line.endswith("|") for line in lines[:2]):
            return False
        return bool(re.match(r"^\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?$", lines[1]))

    async def _get_next_event(self, progress_tracker) -> Dict[str, Any]:
        """获取下一个进度事件"""
        try:
            # 尝试从队列获取事件，超时返回当前状态
            event = await asyncio.wait_for(
                progress_tracker._event_queue.get(), timeout=0.1
            )
            return event.to_dict()
        except asyncio.TimeoutError:
            last_event = getattr(progress_tracker, "_last_event", None)
            if last_event is not None:
                return last_event.to_dict()
            # 超时返回当前状态
            status = progress_tracker.tracker.get_status()
            return {
                "stage": status["stage"],
                "progress": status["progress"],
                "message": progress_tracker._get_current_message(),
                "details": status,
            }

    async def _process_single_page(self, pdf_path: Path, page_num: int) -> PageResult:
        """处理单个页面

        Args:
            pdf_path: PDF文件路径
            page_num: 页码

        Returns:
            页面处理结果
        """
        logger.info(f"开始处理页面 {page_num}")

        # 1. 使用MinerU识别页面结构
        structure = await self._run_mineru_call(
            self.mineru.extract_from_pdf,
            pdf_path,
            pages=[page_num],
        )
        page_structure = structure["pages"][0] if structure["pages"] else None

        if not page_structure:
            raise ValueError(f"页面 {page_num} 结构识别失败")

        # 2. 提取段落块
        original_blocks = self._extract_paragraph_blocks(page_structure, page_num)

        # 3. 批量翻译段落
        translated_blocks = await self._translate_paragraphs(original_blocks)

        # 4. 创建页面结果
        result = PageResult(
            page_num=page_num,
            original_blocks=original_blocks,
            translated_blocks=translated_blocks,
            raw_structure=page_structure,
            processed_at=datetime.now(),
        )

        logger.info(f"页面 {page_num} 处理完成，共 {len(original_blocks)} 个段落")
        return result

    def _extract_paragraph_blocks(
        self, page_structure: Dict[str, Any], page_num: int
    ) -> List[ParagraphBlock]:
        """从页面结构中提取段落块

        Args:
            page_structure: 页面结构
            page_num: 页码

        Returns:
            段落块列表
        """
        blocks = []
        min_length = getattr(self.settings.translation, "min_text_length", 5)

        for i, block in enumerate(page_structure.get("blocks", [])):
            block_type = block.get("type", "text")

            if block_type == "text":
                content = block.get("content", "").strip()
                if content:
                    blocks.append(
                        ParagraphBlock(
                            id=f"page_{page_num}_text_{i}",
                            type="text",
                            original=content,
                            bbox=block.get("bbox", []),
                            page_num=page_num,
                            block_index=i,
                        )
                    )

            elif block_type == "table":
                html_content = (block.get("html") or "").strip()
                markdown_content = (block.get("markdown") or "").strip()
                content = (
                    html_content or markdown_content or block.get("content") or ""
                ).strip()
                if content:
                    blocks.append(
                        ParagraphBlock(
                            id=f"page_{page_num}_table_{i}",
                            type="html_table" if html_content else "table",
                            original=content,
                            bbox=block.get("bbox", []),
                            page_num=page_num,
                            block_index=i,
                        )
                    )

            elif block_type == "figure":
                caption = block.get("caption", "").strip()
                image_ref = (
                    f"images/page_{page_num}_fig_{i}.png" if block.get("image") else ""
                )
                if image_ref and caption:
                    content = f"![{caption}]({image_ref})\n\n*{caption}*"
                elif image_ref:
                    content = f"![image]({image_ref})"
                else:
                    content = caption
                if content:
                    blocks.append(
                        ParagraphBlock(
                            id=f"page_{page_num}_image_{i}",
                            type="image",
                            original=content,
                            bbox=block.get("bbox", []),
                            page_num=page_num,
                            block_index=i,
                        )
                    )

            elif block_type == "formula":
                formula_text = (
                    block.get("latex")
                    or block.get("content")
                    or block.get("text")
                    or ""
                ).strip()
                if formula_text:
                    blocks.append(
                        ParagraphBlock(
                            id=f"page_{page_num}_formula_{i}",
                            type="formula",
                            original=formula_text,
                            bbox=block.get("bbox", []),
                            page_num=page_num,
                            block_index=i,
                        )
                    )

            else:
                content = (block.get("content") or "").strip()
                if content and should_translate_text(content, min_length=min_length):
                    blocks.append(
                        ParagraphBlock(
                            id=f"page_{page_num}_{block_type}_{i}",
                            type=block_type,
                            original=content,
                            bbox=block.get("bbox", []),
                            page_num=page_num,
                            block_index=i,
                        )
                    )

        return blocks

    def _extract_table_paragraphs(
        self, table_block: Dict[str, Any], page_num: int, block_index: int
    ) -> List[ParagraphBlock]:
        """从表格中提取段落块"""
        paragraphs = []

        # 从HTML表格提取单元格内容
        table_html = table_block.get("html", "")
        if table_html:
            import re

            cell_contents = re.findall(
                r"<t[dh][^>]*>(.*?)</t[dh]>", table_html, re.DOTALL
            )

            min_length = getattr(self.settings.translation, "min_text_length", 5)
            for j, content in enumerate(cell_contents):
                # 清理HTML标签
                content = re.sub(r"<[^>]+>", "", content).strip()
                if content and len(content) >= min_length:
                    paragraphs.append(
                        ParagraphBlock(
                            id=f"page_{page_num}_table_{block_index}_cell_{j}",
                            type="table_cell",
                            original=content,
                            page_num=page_num,
                            block_index=block_index,
                        )
                    )

        return paragraphs

    async def _translate_paragraphs(
        self,
        original_blocks: List[ParagraphBlock],
        progress_tracker: Any | None = None,
    ) -> List[ParagraphBlock]:
        """批量翻译段落

        Args:
            original_blocks: 原始段落块列表

        Returns:
            翻译后的段落块列表
        """
        translated_blocks = [
            self._copy_translated_block(block, block.original)
            for block in original_blocks
        ]
        unit_state = self._load_translation_unit_state()
        plans, translation_units = self._build_translation_unit_plans(original_blocks)

        if not translation_units:
            return translated_blocks

        pending_units: list[dict[str, Any]] = []
        state_changed = False
        for unit in translation_units:
            source_hash = unit["source_hash"]
            saved = unit_state.get(unit["id"])
            if (
                saved
                and saved.get("source_hash") == source_hash
                and saved.get("status") in {"translated", "skipped"}
            ):
                unit["translated"] = saved.get("translated", unit["source"])
                unit["status"] = saved.get("status")
                continue
            if not should_translate_text(
                unit["source"],
                min_length=getattr(self.settings.translation, "min_text_length", 5),
            ):
                unit["translated"] = unit["source"]
                unit["status"] = "skipped"
                unit_state[unit["id"]] = self._unit_state_record(unit)
                state_changed = True
                continue
            pending_units.append(unit)

        if state_changed:
            self._save_translation_unit_state(unit_state)

        groups = self._group_translation_units(pending_units)
        logger.info(
            "MinerU structured translation batching: %s units (%s pending) -> %s requests",
            len(translation_units),
            len(pending_units),
            len(groups),
        )

        group_timeout = self._translation_group_timeout_seconds()

        for group_index, group in enumerate(groups, start=1):
            group_chars = sum(len(item["protected_source"]) for item in group)
            self._emit_translation_progress(
                progress_tracker,
                group_index - 1,
                len(groups),
                f"正在批量翻译第 {group_index}/{len(groups)} 组，包含 {len(group)} 个内容单元，约 {group_chars} 字符",
                {
                    "current_group": group_index,
                    "group_units": len(group),
                    "group_chars": group_chars,
                    "timeout_seconds": group_timeout,
                    "status": "started",
                },
            )
            logger.info(
                "MinerU translation group %s/%s started: units=%s chars=%s timeout=%s",
                group_index,
                len(groups),
                len(group),
                group_chars,
                group_timeout,
            )
            started_at = time.monotonic()
            group_status = "completed"
            try:
                translate_call = self._translate_id_unit_group(group)
                if group_timeout:
                    translated_map = await asyncio.wait_for(
                        translate_call,
                        timeout=group_timeout,
                    )
                else:
                    translated_map = await translate_call
            except asyncio.TimeoutError:
                elapsed = time.monotonic() - started_at
                group_status = "timeout"
                logger.warning(
                    "MinerU translation group %s/%s timed out after %.1fs; stopping output generation",
                    group_index,
                    len(groups),
                    elapsed,
                )
                for unit in group:
                    unit["translated"] = unit["source"]
                    unit["status"] = "timeout"
                    unit["error"] = f"timeout after {elapsed:.1f}s"
            except Exception as e:
                elapsed = time.monotonic() - started_at
                group_status = "failed"
                logger.exception(
                    "MinerU translation group %s/%s failed after %.1fs; stopping output generation: %s",
                    group_index,
                    len(groups),
                    elapsed,
                    e,
                )
                for unit in group:
                    unit["translated"] = unit["source"]
                    unit["status"] = "failed"
                    unit["error"] = str(e)
            else:
                elapsed = time.monotonic() - started_at
                logger.info(
                    "MinerU translation group %s/%s completed in %.1fs",
                    group_index,
                    len(groups),
                    elapsed,
                )
                for unit in group:
                    translated = translated_map[unit["id"]]
                    unit["translated"] = restore_markdown_fragments(
                        translated,
                        unit.get("protections") or [],
                    )
                    unit["status"] = "translated"
                    unit["error"] = None

            for unit in group:
                unit_state[unit["id"]] = self._unit_state_record(unit)
            self._save_translation_unit_state(unit_state)

            if group_status == "timeout":
                message = f"第 {group_index}/{len(groups)} 组翻译超时，已停止生成译文（耗时 {elapsed:.1f}s）"
            elif group_status == "failed":
                message = f"第 {group_index}/{len(groups)} 组翻译失败，已停止生成译文（耗时 {elapsed:.1f}s）"
            else:
                message = (
                    f"第 {group_index}/{len(groups)} 组翻译完成（耗时 {elapsed:.1f}s）"
                )

            self._emit_translation_progress(
                progress_tracker,
                group_index,
                len(groups),
                message,
                {
                    "current_group": group_index,
                    "group_units": len(group),
                    "group_chars": group_chars,
                    "elapsed_seconds": round(elapsed, 2),
                    "timeout_seconds": group_timeout,
                    "status": group_status,
                },
            )

            if group_status in {"timeout", "failed"}:
                sample_error = next(
                    (unit.get("error") for unit in group if unit.get("error")), None
                )
                raise RuntimeError(
                    f"MinerU 翻译第 {group_index}/{len(groups)} 组{('超时' if group_status == 'timeout' else '失败')}，"
                    f"未生成伪译文。原因: {sample_error or group_status}"
                )

        for plan in plans:
            block = plan["block"]
            rendered = self._render_unit_template(plan)
            translated_blocks[plan["index"]] = self._copy_translated_block(
                block, rendered
            )

        return translated_blocks

    def _build_translation_unit_plans(
        self,
        original_blocks: list[ParagraphBlock],
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        plans: list[dict[str, Any]] = []
        units: list[dict[str, Any]] = []
        for index, block in enumerate(original_blocks):
            if block.type == "html_table":
                template, block_units = self._extract_html_table_units(block)
            elif block.type in {"formula", "code"}:
                template, block_units = block.original, []
            else:
                template, block_units = self._extract_markdown_text_units(block)
            for unit in block_units:
                unit["block_index"] = index
                units.append(unit)
            plans.append(
                {
                    "index": index,
                    "block": block,
                    "template": template,
                    "units": block_units,
                }
            )
        return plans, units

    def _extract_html_table_units(
        self, block: ParagraphBlock
    ) -> tuple[str, list[dict[str, Any]]]:
        units: list[dict[str, Any]] = []
        unit_counter = 0

        def replace_cell(match: re.Match[str]) -> str:
            nonlocal unit_counter
            start_tag, inner, end_tag = match.group(1), match.group(2), match.group(3)
            pieces = re.split(r"(<[^>]+>)", inner)
            rendered_pieces: list[str] = []
            for piece in pieces:
                if not piece or piece.startswith("<"):
                    rendered_pieces.append(piece)
                    continue
                leading = re.match(r"^\s*", piece).group(0)
                trailing = re.search(r"\s*$", piece).group(0)
                core = piece[
                    len(leading) : len(piece) - len(trailing)
                    if trailing
                    else len(piece)
                ]
                source = html.unescape(core.strip())
                if not source or not should_translate_text(
                    source,
                    min_length=getattr(self.settings.translation, "min_text_length", 5),
                ):
                    rendered_pieces.append(piece)
                    continue
                unit_id = f"{block.id}_cell_{unit_counter:04d}"
                placeholder = self._unit_placeholder(unit_id)
                unit_counter += 1
                units.append(
                    self._make_translation_unit(
                        unit_id,
                        block,
                        source,
                        placeholder,
                        "html_table_cell",
                        escape_html=True,
                    )
                )
                rendered_pieces.append(f"{leading}{placeholder}{trailing}")
            return f"{start_tag}{''.join(rendered_pieces)}{end_tag}"

        template = re.sub(
            r"(<(?:td|th)\b[^>]*>)(.*?)(</(?:td|th)>)",
            replace_cell,
            block.original,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return template, units

    def _extract_markdown_text_units(
        self, block: ParagraphBlock
    ) -> tuple[str, list[dict[str, Any]]]:
        units: list[dict[str, Any]] = []
        rendered_lines: list[str] = []
        in_fence = False
        unit_counter = 0

        for line in block.original.splitlines() or [block.original]:
            stripped = line.strip()
            if stripped.startswith(("```", "~~~")):
                in_fence = not in_fence
                rendered_lines.append(line)
                continue
            if in_fence or stripped.startswith("!["):
                rendered_lines.append(line)
                continue

            prefix = ""
            body = line
            for pattern in (
                r"^(#{1,6}\s+)(.*)$",
                r"^(\s*(?:[-*+]|\d+[.)])\s+)(.*)$",
                r"^(>\s*)(.*)$",
            ):
                matched = re.match(pattern, line)
                if matched:
                    prefix, body = matched.group(1), matched.group(2)
                    break

            if not should_translate_text(
                body,
                min_length=getattr(self.settings.translation, "min_text_length", 5),
            ):
                rendered_lines.append(line)
                continue

            unit_id = f"{block.id}_text_{unit_counter:04d}"
            placeholder = self._unit_placeholder(unit_id)
            unit_counter += 1
            units.append(
                self._make_translation_unit(
                    unit_id, block, body.strip(), placeholder, block.type or "paragraph"
                )
            )
            leading = re.match(r"^\s*", body).group(0)
            trailing = re.search(r"\s*$", body).group(0)
            rendered_lines.append(f"{prefix}{leading}{placeholder}{trailing}")

        return "\n".join(rendered_lines), units

    def _make_translation_unit(
        self,
        unit_id: str,
        block: ParagraphBlock,
        source: str,
        placeholder: str,
        kind: str,
        *,
        escape_html: bool = False,
    ) -> dict[str, Any]:
        protected_source, protections = protect_markdown_fragments(source)
        return {
            "id": unit_id,
            "block_id": block.id,
            "kind": kind,
            "source": source,
            "source_hash": hash_text(source),
            "protected_source": protected_source,
            "protections": protections,
            "placeholder": placeholder,
            "escape_html": escape_html,
            "translated": None,
            "status": "pending",
            "error": None,
        }

    def _unit_placeholder(self, unit_id: str) -> str:
        return f"ZXQUNIT{hash_text(unit_id).upper()}ZXQ"

    def _render_unit_template(self, plan: dict[str, Any]) -> str:
        rendered = plan["template"]
        for unit in plan["units"]:
            translated = unit.get("translated") or unit["source"]
            if unit.get("escape_html"):
                translated = html.escape(translated, quote=False)
            rendered = rendered.replace(unit["placeholder"], translated)
        return rendered

    def _group_translation_units(
        self,
        units: list[dict[str, Any]],
        max_chars: int = 1600,
        max_units: int = 24,
    ) -> list[list[dict[str, Any]]]:
        groups: list[list[dict[str, Any]]] = []
        current_group: list[dict[str, Any]] = []
        current_chars = 0
        for unit in units:
            unit_chars = len(unit["protected_source"]) + len(unit["id"]) + 32
            if current_group and (
                current_chars + unit_chars > max_chars
                or len(current_group) >= max_units
            ):
                groups.append(current_group)
                current_group = [unit]
                current_chars = unit_chars
            else:
                current_group.append(unit)
                current_chars += unit_chars
        if current_group:
            groups.append(current_group)
        return groups

    async def _translate_id_unit_group(
        self, group: list[dict[str, Any]]
    ) -> dict[str, str]:
        payload = {
            "units": [
                {"id": unit["id"], "text": unit["protected_source"]} for unit in group
            ],
        }
        response = await self._call_structured_json_translator(payload)
        translated_map = self._parse_id_unit_translation_response(response, group)
        return translated_map

    async def _call_structured_json_translator(self, payload: dict[str, Any]) -> str:
        if self._supports_openai_chat_translator():
            return await asyncio.to_thread(
                self._call_openai_chat_json_translator, payload
            )
        prompt = self._format_structured_json_prompt(payload)
        return await self._call_translator(prompt)

    def _supports_openai_chat_translator(self) -> bool:
        client = getattr(self.translator, "client", None)
        chat = getattr(client, "chat", None)
        completions = getattr(chat, "completions", None)
        return bool(
            client
            and completions
            and hasattr(completions, "create")
            and getattr(self.translator, "model", None)
        )

    def _call_openai_chat_json_translator(self, payload: dict[str, Any]) -> str:
        rate_limiter = getattr(self.translator, "rate_limiter", None)
        if rate_limiter is not None:
            rate_limiter.wait()

        response = self.translator.client.chat.completions.create(
            model=self.translator.model,
            **self._openai_chat_create_options(payload),
            messages=self._structured_json_messages(payload),
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            with contextlib.suppress(Exception):
                self.translator.token_count.inc(usage.total_tokens)
                self.translator.prompt_token_count.inc(usage.prompt_tokens)
                self.translator.completion_token_count.inc(usage.completion_tokens)
        content = response.choices[0].message.content or ""
        remove_cot = getattr(self.translator, "_remove_cot_content", None)
        if callable(remove_cot):
            content = remove_cot(content)
        return content.strip()

    def _openai_chat_create_options(self, payload: dict[str, Any]) -> dict[str, Any]:
        options = dict(getattr(self.translator, "options", {}) or {})
        if not (self._is_zhipu_glm_translator() or self._is_deepseek_translator()):
            return options

        total_chars = sum(
            len(str(unit.get("text") or "")) for unit in payload.get("units", [])
        )
        estimated_output_tokens = max(
            1024, min(8192, int(total_chars * 1.2) + len(payload.get("units", [])) * 32)
        )
        options.setdefault("max_tokens", estimated_output_tokens)
        options.setdefault("response_format", {"type": "json_object"})
        extra_body = dict(options.get("extra_body") or {})
        if self._is_zhipu_glm_translator():
            extra_body.setdefault("do_sample", False)
            extra_body.setdefault("thinking", {"type": "disabled"})
        if self._is_deepseek_translator():
            extra_body.setdefault("thinking", {"type": "disabled"})
        options["extra_body"] = extra_body
        return options

    def _is_zhipu_glm_translator(self) -> bool:
        model = str(getattr(self.translator, "model", "") or "").lower()
        if model.startswith("glm-"):
            return True
        base_url = str(
            getattr(getattr(self.translator, "client", None), "base_url", "") or ""
        ).lower()
        return "bigmodel.cn" in base_url

    def _is_deepseek_translator(self) -> bool:
        model = str(getattr(self.translator, "model", "") or "").lower()
        if model.startswith("deepseek-"):
            return True
        base_url = str(
            getattr(getattr(self.translator, "client", None), "base_url", "") or ""
        ).lower()
        return "api.deepseek.com" in base_url

    def _structured_json_messages(
        self, payload: dict[str, Any]
    ) -> list[dict[str, str]]:
        target_language = self._display_target_language()
        return [
            {
                "role": "system",
                "content": (
                    "You are a fast, deterministic document translation engine. "
                    "Translate only the text field values. Return strict JSON only."
                ),
            },
            {
                "role": "user",
                "content": self._format_structured_json_prompt(
                    payload, target_language
                ),
            },
        ]

    def _format_structured_json_prompt(
        self,
        payload: dict[str, Any],
        target_language: str | None = None,
    ) -> str:
        target_language = target_language or self._display_target_language()
        source_language = getattr(self.settings.translation, "lang_in", "auto")
        return (
            f"Target language: {target_language}\n"
            f"Source language: {source_language}\n"
            "Task: translate each units[].text value into the target language.\n"
            "Rules:\n"
            '1. Return ONLY valid JSON: {"units":[{"id":"...","text":"..."}]}\n'
            "2. Preserve every id exactly and keep the same unit count.\n"
            "3. Do not translate ids, JSON keys, ZXQKEEP...ZXQ placeholders, or ZXQUNIT...ZXQ placeholders.\n"
            "4. Keep numbers, codes, file names, and proper nouns unchanged when translation is unnecessary.\n"
            "5. Translate labels, headings, sentences, and table-cell text naturally.\n"
            "Input JSON:\n"
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    def _display_target_language(self) -> str:
        lang_out = getattr(self.settings.translation, "lang_out", "zh-CN")
        normalized = str(lang_out).lower().replace("_", "-")
        if normalized in {"zh", "zh-cn", "zh-hans", "chinese", "simplified chinese"}:
            return "Simplified Chinese"
        if normalized in {"zh-tw", "zh-hant", "traditional chinese"}:
            return "Traditional Chinese"
        return str(lang_out)

    def _parse_id_unit_translation_response(
        self,
        response: str,
        group: list[dict[str, Any]],
    ) -> dict[str, str]:
        payload = self._load_json_from_llm_response(response)
        if isinstance(payload, dict) and "units" in payload:
            items = payload.get("units")
        elif isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = [{"id": key, "text": value} for key, value in payload.items()]
        else:
            raise ValueError("LLM response is not a JSON object/list")

        if not isinstance(items, list):
            raise ValueError("LLM response units is not a list")
        translated_map: dict[str, str] = {}
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("LLM response unit is not an object")
            unit_id = str(item.get("id") or "").strip()
            text = item.get("text")
            if text is None:
                text = item.get("translation")
            if not unit_id or text is None:
                raise ValueError("LLM response unit misses id/text")
            if unit_id in translated_map:
                raise ValueError(f"LLM response has duplicate id: {unit_id}")
            translated_map[unit_id] = str(text)

        expected_ids = {unit["id"] for unit in group}
        actual_ids = set(translated_map)
        if actual_ids != expected_ids:
            missing = sorted(expected_ids - actual_ids)[:5]
            extra = sorted(actual_ids - expected_ids)[:5]
            raise ValueError(
                f"LLM response id mismatch: missing={missing}, extra={extra}"
            )
        return translated_map

    def _load_json_from_llm_response(self, response: str) -> Any:
        text = (response or "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
            text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start_candidates = [
                idx for idx in [text.find("{"), text.find("[")] if idx >= 0
            ]
            if not start_candidates:
                raise
            start = min(start_candidates)
            end = max(text.rfind("}"), text.rfind("]"))
            if end <= start:
                raise
            return json.loads(text[start : end + 1])

    def _translation_unit_state_path(self) -> Path:
        mineru_dir = getattr(self, "mineru_dir", None) or Path.cwd() / "mineru"
        mineru_dir.mkdir(parents=True, exist_ok=True)
        return mineru_dir / "translation_units_state.jsonl"

    def _load_translation_unit_state(self) -> dict[str, dict[str, Any]]:
        state_path = self._translation_unit_state_path()
        if not state_path.exists():
            return {}
        state: dict[str, dict[str, Any]] = {}
        for line in state_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            unit_id = record.get("id")
            if unit_id:
                state[str(unit_id)] = record
        return state

    def _save_translation_unit_state(self, state: dict[str, dict[str, Any]]) -> None:
        state_path = self._translation_unit_state_path()
        lines = [
            json.dumps(record, ensure_ascii=False, sort_keys=True)
            for _, record in sorted(state.items())
        ]
        state_path.write_text(
            "\n".join(lines) + ("\n" if lines else ""), encoding="utf-8"
        )

    def _unit_state_record(self, unit: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": unit["id"],
            "block_id": unit["block_id"],
            "kind": unit["kind"],
            "source_hash": unit["source_hash"],
            "source": unit["source"],
            "translated": unit.get("translated") or unit["source"],
            "status": unit.get("status") or "pending",
            "error": unit.get("error"),
            "updated_at": datetime.now().isoformat(),
        }

    def _translation_group_timeout_seconds(self) -> float | None:
        configured = None
        mineru_settings = getattr(self.settings, "mineru", None)
        if mineru_settings is not None:
            configured = getattr(
                mineru_settings,
                "translation_group_timeout_seconds",
                None,
            )
        if configured in (None, ""):
            configured = os.getenv("PDF2ZH_MINERU_TRANSLATION_GROUP_TIMEOUT_SECONDS")
        if configured in (None, ""):
            configured = 300
        try:
            timeout = float(configured)
        except (TypeError, ValueError):
            timeout = 300.0
        return timeout if timeout > 0 else None

    def _mineru_timeout_seconds(self) -> float | None:
        try:
            timeout = float(self.mineru_timeout_seconds)
        except (TypeError, ValueError):
            timeout = 0.0
        return timeout if timeout > 0 else None

    def _local_extraction_progress(
        self, completed_pages: int, total_pages: int
    ) -> float:
        if total_pages <= 0:
            return LOCAL_EXTRACTION_PROGRESS_START
        ratio = max(0.0, min(completed_pages / total_pages, 1.0))
        return (
            LOCAL_EXTRACTION_PROGRESS_START
            + (LOCAL_EXTRACTION_PROGRESS_END - LOCAL_EXTRACTION_PROGRESS_START) * ratio
        )

    def _copy_translated_block(
        self, block: ParagraphBlock, translated: str
    ) -> ParagraphBlock:
        return ParagraphBlock(
            id=block.id,
            type=block.type,
            original=block.original,
            translated=translated,
            bbox=block.bbox,
            page_num=block.page_num,
            block_index=block.block_index,
        )

    def _group_translation_items(
        self,
        translation_items: list[dict[str, Any]],
        max_chars: int = 6000,
    ) -> list[list[dict[str, Any]]]:
        groups: list[list[dict[str, Any]]] = []
        current_group: list[dict[str, Any]] = []
        current_chars = 0

        for item in translation_items:
            item_chars = len(item["protected_text"])
            if current_group and current_chars + item_chars > max_chars:
                groups.append(current_group)
                current_group = [item]
                current_chars = item_chars
            else:
                current_group.append(item)
                current_chars += item_chars

        if current_group:
            groups.append(current_group)

        return groups

    async def _translate_protected_group(
        self, group: list[dict[str, Any]]
    ) -> list[str]:
        if len(group) == 1:
            item = group[0]
            translated = await self._call_translator(item["protected_text"])
            return [restore_markdown_fragments(translated, item["protections"])]

        separator_token = f"ZXQBLOCKSEPARATOR{uuid.uuid4().hex.upper()}ZXQ"
        combined_text = f"\n{separator_token}\n".join(
            item["protected_text"] for item in group
        )
        translated_combined = await self._call_translator(combined_text)
        translated_parts = re.split(
            rf"\s*{re.escape(separator_token)}\s*",
            translated_combined,
        )
        if len(translated_parts) != len(group):
            logger.warning(
                "批量翻译分隔符恢复失败: expected=%s actual=%s",
                len(group),
                len(translated_parts),
            )
            return await self._translate_group_individually(group)

        return [
            restore_markdown_fragments(translated.strip(), item["protections"])
            for item, translated in zip(group, translated_parts, strict=False)
        ]

    async def _translate_group_individually(
        self, group: list[dict[str, Any]]
    ) -> list[str]:
        translated_texts: list[str] = []
        for item in group:
            try:
                translated = await self._call_translator(item["protected_text"])
                translated_texts.append(
                    restore_markdown_fragments(translated, item["protections"])
                )
            except Exception as e:
                logger.error("单元翻译失败，保留原文: %s", e)
                translated_texts.append(item["block"].original)
        return translated_texts

    async def _call_translator(self, protected_text: str) -> str:
        if not hasattr(self.translator, "translate"):
            logger.error(f"翻译引擎 {self.translator} 没有 translate 方法")
            return protected_text

        if asyncio.iscoroutinefunction(self.translator.translate):
            return await self.translator.translate(protected_text)
        return await asyncio.to_thread(self.translator.translate, protected_text)

    def _emit_translation_progress(
        self,
        progress_tracker: Any | None,
        completed_groups: int,
        total_groups: int,
        message: str,
        extra_details: dict[str, Any] | None = None,
    ) -> None:
        if not progress_tracker or total_groups <= 0:
            return
        from .progress_tracker import ProgressEvent, ProcessingStage

        progress = 0.85 + (completed_groups / total_groups) * 0.10
        details = {
            "completed_groups": completed_groups,
            "total_groups": total_groups,
        }
        if extra_details:
            details.update(extra_details)
        progress_tracker.put_event(
            ProgressEvent(
                stage=ProcessingStage.TRANSLATION,
                progress=min(progress, 0.95),
                message=message,
                details=details,
                total_pages=1,
            )
        )

    async def _translate_markdown_unit_text(self, text: str) -> str:
        """Translate one Markdown text unit while protecting fragile syntax."""
        min_length = getattr(self.settings.translation, "min_text_length", 5)
        if not should_translate_text(text, min_length=min_length):
            return text

        protected_text, protections = protect_markdown_fragments(text)

        if not hasattr(self.translator, "translate"):
            logger.error(f"翻译引擎 {self.translator} 没有 translate 方法")
            return text

        if asyncio.iscoroutinefunction(self.translator.translate):
            translated = await self.translator.translate(protected_text)
        else:
            translated = await asyncio.to_thread(
                self.translator.translate, protected_text
            )

        return restore_markdown_fragments(translated, protections)

    async def _run_mineru_call(self, func: Callable, *args, **kwargs):
        call = asyncio.to_thread(func, *args, **kwargs)
        timeout = self._mineru_timeout_seconds()
        if timeout:
            return await asyncio.wait_for(call, timeout=timeout)
        return await call

    def _translator_name(self) -> str:
        return getattr(self.translator, "name", type(self.translator).__name__)

    async def _save_page_result(self, result: PageResult):
        """保存页面结果到文件"""
        result_file = self.page_results_dir / f"page_{result.page_num}.json"

        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result.to_dict(), f, ensure_ascii=False, indent=2)

        logger.debug(f"保存页面结果: {result_file}")

    async def _load_page_result(self, page_num: int) -> Optional[PageResult]:
        """加载页面结果"""
        result_file = self.page_results_dir / f"page_{page_num}.json"

        if not result_file.exists():
            return None

        try:
            with open(result_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 转换为PageResult对象
            original_blocks = [
                ParagraphBlock.from_dict(block) for block in data["original_blocks"]
            ]
            translated_blocks = [
                ParagraphBlock.from_dict(block) for block in data["translated_blocks"]
            ]

            return PageResult(
                page_num=data["page_num"],
                original_blocks=original_blocks,
                translated_blocks=translated_blocks,
                raw_structure=data["raw_structure"],
                processed_at=datetime.fromisoformat(data["processed_at"]),
            )

        except Exception as e:
            logger.error(f"加载页面结果失败 {page_num}: {e}")
            return None

    async def _load_cached_results(
        self, page_numbers: List[int]
    ) -> Dict[int, PageResult]:
        """加载缓存结果"""
        cached = {}

        for page_num in page_numbers:
            result = await self._load_page_result(page_num)
            if result:
                cached[page_num] = result

        logger.info(f"加载了 {len(cached)} 个缓存页面结果")
        return cached

    async def _load_all_page_results(self, page_numbers: List[int]) -> List[PageResult]:
        """加载所有页面结果"""
        results = []

        for page_num in page_numbers:
            result = await self._load_page_result(page_num)
            if result:
                results.append(result)
            else:
                logger.warning(f"页面 {page_num} 结果不存在")

        # 按页码排序
        results.sort(key=lambda x: x.page_num)
        return results

    async def _generate_outputs(self, page_results: List[PageResult]):
        """生成各种格式的输出文件"""
        logger.info("开始生成输出文件...")

        generated_at = datetime.now()
        output_prefix = generated_at.strftime("%Y%m%d_%H%M%S")

        def output_name(file_name: str) -> str:
            return f"{output_prefix}_{file_name}"

        min_length = getattr(self.settings.translation, "min_text_length", 5)

        # 0. 保存 MinerU 原始结构、原文 Markdown 和稳定翻译单元。
        await self._save_extracted_images(page_results)

        raw_structure = build_raw_structure_payload(page_results)
        self.storage.save_result(
            self.project_id,
            "mineru",
            output_name("raw_structure.json"),
            json_dumps_safe(raw_structure),
        )

        source_md = build_source_markdown(page_results)
        source_md = self._prepare_markdown_assets(source_md, page_results)
        self.storage.save_result(
            self.project_id, "mineru", output_name("source.md"), source_md
        )

        translation_units = build_translation_units(page_results, min_length=min_length)
        self.storage.save_result(
            self.project_id,
            "mineru",
            output_name("translation_units.jsonl"),
            translation_units_to_jsonl(translation_units),
        )

        translation_map = build_translation_map(page_results, min_length=min_length)
        translation_map["metadata"] = {
            "project_id": self.project_id,
            "source_language": self.settings.translation.lang_in,
            "target_language": self.settings.translation.lang_out,
            "translation_engine": getattr(
                self.translator, "name", type(self.translator).__name__
            ),
            "total_pages": len(page_results),
            "generated_at": generated_at.isoformat(timespec="seconds"),
            "output_prefix": output_prefix,
        }
        self.storage.save_result(
            self.project_id,
            "mineru",
            output_name("translation_map.json"),
            json_dumps_safe(translation_map),
        )

        # 1. 生成段落级双语对照Markdown
        bilingual_md = self._generate_bilingual_markdown(page_results)
        bilingual_md = self._prepare_markdown_assets(bilingual_md, page_results)
        self.storage.save_result(
            self.project_id, "mineru", output_name("bilingual.md"), bilingual_md
        )
        self.storage.save_result(
            self.project_id,
            "mineru",
            output_name("bilingual_self_contained.md"),
            self._make_self_contained_markdown(bilingual_md, page_results),
        )

        # 2. 生成纯译文Markdown
        translated_md = self._generate_translated_markdown(page_results)
        translated_md = self._prepare_markdown_assets(translated_md, page_results)
        self.storage.save_result(
            self.project_id, "mineru", output_name("translated.md"), translated_md
        )
        self.storage.save_result(
            self.project_id,
            "mineru",
            output_name("translated_self_contained.md"),
            self._make_self_contained_markdown(translated_md, page_results),
        )

        # 3. 生成双语对照HTML
        bilingual_html = self._generate_bilingual_html(page_results)
        self.storage.save_result(
            self.project_id, "mineru", output_name("bilingual.html"), bilingual_html
        )

        # 4. 生成纯译文HTML
        translated_html = self._generate_translated_html(page_results)
        self.storage.save_result(
            self.project_id, "mineru", output_name("translated.html"), translated_html
        )

        # 5. 生成标准 A4 纯译文 PDF
        translated_pdf = markdown_to_a4_pdf_bytes(
            translated_md,
            title=f"{output_prefix} {self.project_id} translated",
            base_dir=self.mineru_dir,
        )
        self.storage.save_result(
            self.project_id, "mineru", output_name("translated.pdf"), translated_pdf
        )

        # 6. 生成结构化JSON数据
        structured_json = self._generate_structured_json(page_results)
        self.storage.save_result(
            self.project_id, "mineru", output_name("structured.json"), structured_json
        )

        logger.info("输出文件生成完成")

    def _markdown_image_base_dirs(self, page_results: List[PageResult]) -> list[Path]:
        base_dirs: list[Path] = [
            self.mineru_dir,
            self.mineru_dir / "images",
        ]
        for result in page_results:
            raw_structure = result.raw_structure or {}
            mineru_online = raw_structure.get("mineru_online") or {}
            artifacts = mineru_online.get("artifacts") or {}
            for key in ("extract_dir", "markdown", "zip"):
                value = artifacts.get(key)
                if not value:
                    continue
                path = Path(value)
                base_dir = path if path.is_dir() else path.parent
                base_dirs.extend([base_dir, base_dir / "images"])
        return base_dirs

    def _prepare_markdown_assets(
        self,
        markdown_content: str,
        page_results: List[PageResult],
    ) -> str:
        prepared, copied = copy_markdown_images_to_dir(
            markdown_content,
            source_base_dirs=self._markdown_image_base_dirs(page_results),
            target_base_dir=self.mineru_dir,
            target_prefix="images",
        )
        if copied:
            logger.info(
                "已归档 Markdown 图片 %s 个到 %s", copied, self.mineru_dir / "images"
            )
        return prepared

    def _make_self_contained_markdown(
        self,
        markdown_content: str,
        page_results: List[PageResult],
    ) -> str:
        return embed_markdown_images_as_data_uris(
            markdown_content,
            base_dirs=self._markdown_image_base_dirs(page_results),
        )

    async def _save_extracted_images(self, page_results: List[PageResult]):
        """Persist figure images referenced by source.md when MinerU returns PIL images."""
        images_dir = self.mineru_dir / "images"
        images_dir.mkdir(parents=True, exist_ok=True)

        for result in page_results:
            raw_structure = result.raw_structure or {}
            for index, block in enumerate(raw_structure.get("blocks", [])):
                if block.get("type") != "figure":
                    continue
                image = block.get("image")
                if not hasattr(image, "save"):
                    continue
                image_path = images_dir / f"page_{result.page_num}_fig_{index}.png"
                try:
                    image.save(image_path)
                    logger.debug(f"保存MinerU图片: {image_path}")
                except Exception as e:
                    logger.warning(f"保存MinerU图片失败 {image_path}: {e}")

    def _generate_bilingual_markdown(self, page_results: List[PageResult]) -> str:
        """生成段落级双语对照Markdown"""
        lines = []

        # 文档头部
        lines.append("# 文档翻译 - 段落级双语对照")
        lines.append("")
        lines.append(f"**源语言**: {self.settings.translation.lang_in}")
        lines.append(f"**目标语言**: {self.settings.translation.lang_out}")
        lines.append(f"**翻译引擎**: {self._translator_name()}")
        lines.append(f"**处理时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for result in page_results:
            lines.append(f"## 第 {result.page_num} 页")
            lines.append("")

            for block in result.translated_blocks:
                if block.type == "text":
                    lines.append("### 📝 文本段落")
                elif block.type == "caption":
                    lines.append("### 🖼️ 图片说明")
                elif block.type == "table_cell":
                    lines.append("### 📊 表格内容")
                elif block.type == "formula_caption":
                    lines.append("### 📐 公式说明")
                else:
                    lines.append("### 📄 内容")

                lines.append("")

                # 原文
                lines.append("**原文:**")
                lines.append("")
                lines.append(f"> {block.original}")
                lines.append("")

                # 译文
                lines.append("**译文:**")
                lines.append("")
                lines.append(f"{block.translated or block.original}")
                lines.append("")

                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def _generate_translated_markdown(self, page_results: List[PageResult]) -> str:
        """生成纯译文Markdown"""
        lines = []

        # 文档头部
        lines.append("# 翻译文档")
        lines.append("")
        lines.append(f"**源语言**: {self.settings.translation.lang_in}")
        lines.append(f"**目标语言**: {self.settings.translation.lang_out}")
        lines.append(f"**翻译引擎**: {self._translator_name()}")
        lines.append("")
        lines.append("---")
        lines.append("")

        for result in page_results:
            lines.append(f"## 第 {result.page_num} 页")
            lines.append("")

            for block in result.translated_blocks:
                content = block.translated or block.original

                if block.type == "text":
                    lines.append(content)
                elif block.type == "caption":
                    lines.append(f"*{content}*")
                else:
                    lines.append(content)

                lines.append("")

        return "\n".join(lines)

    def _generate_bilingual_html(self, page_results: List[PageResult]) -> str:
        """生成双语对照HTML"""
        html_parts = []

        # HTML头部
        html_parts.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>双语对照文档</title>
    <style>
        body {
            font-family: 'Inter', sans-serif;
            max-width: 1000px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            background: #fafafa;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }
        .page {
            background: white;
            margin-bottom: 30px;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .page-title {
            color: #333;
            border-bottom: 3px solid #667eea;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .paragraph {
            margin-bottom: 25px;
            padding: 20px;
            border-left: 4px solid #667eea;
            background: #f8f9ff;
            border-radius: 0 8px 8px 0;
        }
        .paragraph-type {
            font-weight: 600;
            color: #667eea;
            margin-bottom: 10px;
            font-size: 0.9em;
        }
        .original {
            background: #fff3cd;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 10px;
            font-style: italic;
            color: #856404;
        }
        .translated {
            background: #d1ecf1;
            padding: 15px;
            border-radius: 6px;
            color: #0c5460;
        }
        .original-label, .translated-label {
            font-weight: 600;
            margin-bottom: 5px;
            font-size: 0.85em;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📄 双语对照文档</h1>
        <p>源语言: {lang_from} → 目标语言: {lang_to}</p>
        <p>翻译引擎: {engine}</p>
        <p>生成时间: {time}</p>
    </div>""")
        html_parts[-1] = (
            html_parts[-1]
            .replace("{lang_from}", self.settings.translation.lang_in)
            .replace("{lang_to}", self.settings.translation.lang_out)
            .replace("{engine}", self._translator_name())
            .replace("{time}", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

        for result in page_results:
            html_parts.append(f'<div class="page">')
            html_parts.append(f'<h2 class="page-title">第 {result.page_num} 页</h2>')

            for block in result.translated_blocks:
                # 段落类型
                type_map = {
                    "text": "📝 文本段落",
                    "caption": "🖼️ 图片说明",
                    "table_cell": "📊 表格内容",
                    "formula_caption": "📐 公式说明",
                }

                paragraph_type = type_map.get(block.type, "📄 内容")

                html_parts.append(f'<div class="paragraph">')
                html_parts.append(f'<div class="paragraph-type">{paragraph_type}</div>')

                # 原文
                html_parts.append(f'<div class="original-label">原文:</div>')
                html_parts.append(f'<div class="original">{block.original}</div>')

                # 译文
                html_parts.append(f'<div class="translated-label">译文:</div>')
                html_parts.append(
                    f'<div class="translated">{block.translated or block.original}</div>'
                )

                html_parts.append(f"</div>")

            html_parts.append(f"</div>")

        html_parts.append("</body></html>")

        return "\n".join(html_parts)

    def _generate_translated_html(self, page_results: List[PageResult]) -> str:
        """生成纯译文HTML"""
        html_parts = []

        # HTML头部
        html_parts.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>翻译文档</title>
    <style>
        body {
            font-family: 'Inter', sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            background: #fafafa;
        }
        .header {
            background: linear-gradient(135deg, #28a745 0%, #20c997 100%);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: center;
        }
        .page {
            background: white;
            margin-bottom: 30px;
            padding: 30px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .page-title {
            color: #333;
            border-bottom: 3px solid #28a745;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .paragraph {
            margin-bottom: 15px;
            padding: 10px 0;
        }
        .caption {
            font-style: italic;
            color: #666;
            text-align: center;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📄 翻译文档</h1>
        <p>源语言: {lang_from} → 目标语言: {lang_to}</p>
        <p>翻译引擎: {engine}</p>
    </div>""")
        html_parts[-1] = (
            html_parts[-1]
            .replace("{lang_from}", self.settings.translation.lang_in)
            .replace("{lang_to}", self.settings.translation.lang_out)
            .replace("{engine}", self._translator_name())
        )

        for result in page_results:
            html_parts.append(f'<div class="page">')
            html_parts.append(f'<h2 class="page-title">第 {result.page_num} 页</h2>')

            for block in result.translated_blocks:
                content = block.translated or block.original

                if block.type == "caption":
                    html_parts.append(f'<div class="caption">{content}</div>')
                else:
                    html_parts.append(f'<div class="paragraph">{content}</div>')

            html_parts.append(f"</div>")

        html_parts.append("</body></html>")

        return "\n".join(html_parts)

    def _generate_structured_json(self, page_results: List[PageResult]) -> str:
        """生成结构化JSON数据"""
        structured_data = {
            "metadata": {
                "project_id": self.project_id,
                "source_language": self.settings.translation.lang_in,
                "target_language": self.settings.translation.lang_out,
                "translation_engine": getattr(
                    self.translator, "name", type(self.translator).__name__
                ),
                "total_pages": len(page_results),
                "processed_at": datetime.now().isoformat(),
            },
            "pages": [],
        }

        for result in page_results:
            page_data = {
                "page_num": result.page_num,
                "processed_at": result.processed_at.isoformat(),
                "paragraphs": [block.to_dict() for block in result.translated_blocks],
                "raw_structure": to_json_safe(result.raw_structure),
            }
            structured_data["pages"].append(page_data)

        return json.dumps(structured_data, ensure_ascii=False, indent=2)

    def _resolve_pages(
        self,
        pdf_path: Path,
        explicit_pages: Optional[List[int]],
        range_expr: Optional[str],
    ) -> List[int]:
        """解析页码范围"""
        import fitz

        with fitz.open(pdf_path) as document:
            total = document.page_count

        if explicit_pages:
            return [p for p in explicit_pages if 1 <= p <= total]

        if range_expr:
            selected = []
            for chunk in range_expr.split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if "-" in chunk:
                    start, end = chunk.split("-", 1)
                    selected.extend(range(int(start), int(end) + 1))
                else:
                    selected.append(int(chunk))
            return [p for p in selected if 1 <= p <= total]

        return list(range(1, total + 1))
