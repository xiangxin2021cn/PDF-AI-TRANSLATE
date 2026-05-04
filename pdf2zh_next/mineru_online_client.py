from __future__ import annotations

import logging
import os
import re
import time
import uuid
import zipfile
from dataclasses import dataclass
from dataclasses import field
from pathlib import Path
from typing import Any
from typing import Callable

import requests

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[float, str, dict[str, Any] | None], None]


class MinerUOnlineAPIError(RuntimeError):
    pass


@dataclass
class MinerUOnlineResult:
    markdown: str
    raw_payload: dict[str, Any]
    artifacts: dict[str, str] = field(default_factory=dict)
    source: str = ""
    backend: str = ""


class MinerUOnlineClient:
    """Client for MinerU official online parsing APIs.

    Supported modes:
    - online-api: precise v4 API, token required, returns a zip with Markdown/JSON.
    - online-agent: lightweight v1 Agent API, no token, returns Markdown URL.
    """

    PRECISE_MODE = "online-api"
    AGENT_MODE = "online-agent"

    def __init__(
        self,
        *,
        base_url: str = "https://mineru.net",
        mode: str = PRECISE_MODE,
        token: str | None = None,
        model_version: str = "vlm",
        language: str = "ch",
        is_ocr: bool = True,
        enable_formula: bool = True,
        enable_table: bool = True,
        timeout_seconds: int = 600,
        poll_interval_seconds: int = 3,
        no_cache: bool = False,
        cache_tolerance: int = 900,
        session: requests.Session | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/") or "https://mineru.net"
        self.mode = mode
        self.token = (token or os.getenv("MINERU_API_TOKEN") or "").strip()
        self.model_version = model_version or "vlm"
        self.language = language or "ch"
        self.is_ocr = bool(is_ocr)
        self.enable_formula = bool(enable_formula)
        self.enable_table = bool(enable_table)
        self.timeout_seconds = int(timeout_seconds or 600)
        self.poll_interval_seconds = max(1, int(poll_interval_seconds or 3))
        self.no_cache = bool(no_cache)
        self.cache_tolerance = int(cache_tolerance or 900)
        self.session = session or requests.Session()

    def extract_file(
        self,
        file_path: str | Path,
        *,
        page_range: str | None = None,
        artifact_dir: str | Path | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> MinerUOnlineResult:
        file_path = Path(file_path)
        if self.mode == self.AGENT_MODE:
            return self._extract_agent_file(
                file_path,
                page_range=page_range,
                artifact_dir=artifact_dir,
                progress_callback=progress_callback,
            )
        if self.mode == self.PRECISE_MODE:
            return self._extract_precise_file(
                file_path,
                page_range=page_range,
                artifact_dir=artifact_dir,
                progress_callback=progress_callback,
            )
        raise ValueError(f"Unsupported MinerU online mode: {self.mode}")

    def _extract_precise_file(
        self,
        file_path: Path,
        *,
        page_range: str | None,
        artifact_dir: str | Path | None,
        progress_callback: ProgressCallback | None,
    ) -> MinerUOnlineResult:
        if not self.token:
            raise ValueError("MinerU precise API requires a token. Set it in UI or MINERU_API_TOKEN.")

        artifact_path = self._prepare_artifact_dir(artifact_dir)
        data_id = self._make_data_id(file_path)
        self._emit(progress_callback, 0.03, "正在申请 MinerU 精准 API 上传链接...", None)

        file_payload: dict[str, Any] = {
            "name": file_path.name,
            "data_id": data_id,
            "is_ocr": self.is_ocr,
        }
        if page_range:
            file_payload["page_ranges"] = page_range

        payload: dict[str, Any] = {
            "files": [file_payload],
            "model_version": self.model_version,
            "language": self.language,
            "enable_formula": self.enable_formula,
            "enable_table": self.enable_table,
        }
        if self.no_cache:
            payload["no_cache"] = True
        if self.cache_tolerance > 0:
            payload["cache_tolerance"] = self.cache_tolerance

        submit_payload = self._post_json(
            f"{self.base_url}/api/v4/file-urls/batch",
            payload,
            headers=self._auth_headers(),
        )
        data = submit_payload.get("data") or {}
        batch_id = data.get("batch_id")
        upload_urls = data.get("file_urls") or []
        if not batch_id or not upload_urls:
            raise MinerUOnlineAPIError(f"MinerU upload URL response is incomplete: {submit_payload}")

        self._emit(progress_callback, 0.10, "正在上传文件到 MinerU 官方存储...", {"batch_id": batch_id})
        self._upload_file(upload_urls[0], file_path)
        self._emit(progress_callback, 0.18, "文件上传完成，等待 MinerU 精准解析...", {"batch_id": batch_id})

        result_payload = self._poll_precise_result(batch_id, data_id, progress_callback)
        extract_result = self._find_precise_extract_result(result_payload, data_id)
        zip_url = extract_result.get("full_zip_url")
        if not zip_url:
            raise MinerUOnlineAPIError(f"MinerU precise result has no full_zip_url: {extract_result}")

        self._emit(progress_callback, 0.72, "正在下载 MinerU 解析结果 zip...", {"batch_id": batch_id})
        zip_path = artifact_path / "mineru_precise_result.zip"
        self._download_binary(zip_url, zip_path)
        extract_dir = artifact_path / "precise_extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path) as archive:
            archive.extractall(extract_dir)

        markdown_path = self._find_first_file(extract_dir, ["full.md", "*.md"])
        if not markdown_path:
            raise MinerUOnlineAPIError("MinerU precise zip does not contain Markdown output")

        markdown = markdown_path.read_text(encoding="utf-8")
        raw_payload = {
            "mode": self.PRECISE_MODE,
            "submit": submit_payload,
            "result": result_payload,
            "extract_result": extract_result,
            "full_zip_url": zip_url,
            "data_id": data_id,
        }
        artifacts = {
            "zip": str(zip_path),
            "extract_dir": str(extract_dir),
            "markdown": str(markdown_path),
        }
        self._emit(progress_callback, 0.80, "MinerU 精准 API 解析结果已下载", {"batch_id": batch_id})
        return MinerUOnlineResult(
            markdown=markdown,
            raw_payload=raw_payload,
            artifacts=artifacts,
            source=str(file_path),
            backend=self.PRECISE_MODE,
        )

    def _extract_agent_file(
        self,
        file_path: Path,
        *,
        page_range: str | None,
        artifact_dir: str | Path | None,
        progress_callback: ProgressCallback | None,
    ) -> MinerUOnlineResult:
        artifact_path = self._prepare_artifact_dir(artifact_dir)
        agent_page_range = self._normalize_agent_page_range(page_range)
        payload: dict[str, Any] = {
            "file_name": file_path.name,
            "language": self.language,
            "enable_table": self.enable_table,
            "is_ocr": self.is_ocr,
            "enable_formula": self.enable_formula,
        }
        if agent_page_range:
            payload["page_range"] = agent_page_range

        self._emit(progress_callback, 0.03, "正在申请 MinerU Agent 上传链接...", None)
        submit_payload = self._post_json(f"{self.base_url}/api/v1/agent/parse/file", payload)
        data = submit_payload.get("data") or {}
        task_id = data.get("task_id")
        upload_url = data.get("file_url")
        if not task_id or not upload_url:
            raise MinerUOnlineAPIError(f"MinerU Agent upload response is incomplete: {submit_payload}")

        self._emit(progress_callback, 0.10, "正在上传文件到 MinerU Agent 存储...", {"task_id": task_id})
        self._upload_file(upload_url, file_path)
        self._emit(progress_callback, 0.18, "文件上传完成，等待 MinerU Agent 解析...", {"task_id": task_id})

        result_payload = self._poll_agent_result(task_id, progress_callback)
        result_data = result_payload.get("data") or {}
        markdown_url = result_data.get("markdown_url")
        if not markdown_url:
            raise MinerUOnlineAPIError(f"MinerU Agent result has no markdown_url: {result_payload}")

        self._emit(progress_callback, 0.72, "正在下载 MinerU Agent Markdown...", {"task_id": task_id})
        markdown_path = artifact_path / "mineru_agent_full.md"
        markdown = self._download_text(markdown_url)
        markdown_path.write_text(markdown, encoding="utf-8")

        raw_payload = {
            "mode": self.AGENT_MODE,
            "submit": submit_payload,
            "result": result_payload,
            "markdown_url": markdown_url,
            "task_id": task_id,
        }
        artifacts = {"markdown": str(markdown_path)}
        self._emit(progress_callback, 0.80, "MinerU Agent Markdown 已下载", {"task_id": task_id})
        return MinerUOnlineResult(
            markdown=markdown,
            raw_payload=raw_payload,
            artifacts=artifacts,
            source=str(file_path),
            backend=self.AGENT_MODE,
        )

    def _poll_precise_result(
        self,
        batch_id: str,
        data_id: str,
        progress_callback: ProgressCallback | None,
    ) -> dict[str, Any]:
        deadline = time.time() + self.timeout_seconds
        last_payload: dict[str, Any] = {}
        while time.time() < deadline:
            payload = self._get_json(
                f"{self.base_url}/api/v4/extract-results/batch/{batch_id}",
                headers=self._auth_headers(accept_only=True),
            )
            last_payload = payload
            extract_result = self._find_precise_extract_result(payload, data_id)
            state = extract_result.get("state", "unknown")
            progress = extract_result.get("extract_progress") or {}
            message = self._format_precise_state(state, progress)
            self._emit(progress_callback, 0.20, message, {"batch_id": batch_id, "state": state, "progress": progress})

            if state == "done":
                return payload
            if state == "failed":
                raise MinerUOnlineAPIError(extract_result.get("err_msg") or "MinerU precise parsing failed")
            time.sleep(self.poll_interval_seconds)

        raise TimeoutError(f"MinerU precise API polling timed out. Last response: {last_payload}")

    def _poll_agent_result(
        self,
        task_id: str,
        progress_callback: ProgressCallback | None,
    ) -> dict[str, Any]:
        deadline = time.time() + self.timeout_seconds
        last_payload: dict[str, Any] = {}
        while time.time() < deadline:
            payload = self._get_json(f"{self.base_url}/api/v1/agent/parse/{task_id}")
            last_payload = payload
            data = payload.get("data") or {}
            state = data.get("state", "unknown")
            self._emit(progress_callback, 0.20, f"MinerU Agent 状态: {state}", {"task_id": task_id, "state": state})
            if state == "done":
                return payload
            if state == "failed":
                raise MinerUOnlineAPIError(data.get("err_msg") or "MinerU Agent parsing failed")
            time.sleep(self.poll_interval_seconds)

        raise TimeoutError(f"MinerU Agent API polling timed out. Last response: {last_payload}")

    def _post_json(
        self,
        url: str,
        payload: dict[str, Any],
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        request_headers = {"Content-Type": "application/json", "Accept": "*/*"}
        if headers:
            request_headers.update(headers)
        response = self.session.post(url, headers=request_headers, json=payload, timeout=30)
        return self._decode_response(response)

    def _get_json(self, url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
        response = self.session.get(url, headers=headers or {"Accept": "*/*"}, timeout=30)
        return self._decode_response(response)

    def _decode_response(self, response: requests.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
            payload = response.json()
        except Exception as exc:
            raise MinerUOnlineAPIError(f"MinerU API HTTP {response.status_code}: {response.text[:500]}") from exc
        if payload.get("code") not in (0, "0"):
            raise MinerUOnlineAPIError(f"MinerU API error {payload.get('code')}: {payload.get('msg')}")
        return payload

    def _upload_file(self, upload_url: str, file_path: Path) -> None:
        with file_path.open("rb") as file_obj:
            response = self.session.put(upload_url, data=file_obj, timeout=max(60, self.timeout_seconds))
        if response.status_code not in (200, 201):
            raise MinerUOnlineAPIError(f"MinerU file upload failed HTTP {response.status_code}: {response.text[:500]}")

    def _download_binary(self, url: str, save_path: Path) -> None:
        with self.session.get(url, stream=True, timeout=max(60, self.timeout_seconds)) as response:
            response.raise_for_status()
            with save_path.open("wb") as file_obj:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if chunk:
                        file_obj.write(chunk)

    def _download_text(self, url: str) -> str:
        response = self.session.get(url, timeout=max(60, self.timeout_seconds))
        response.raise_for_status()
        response.encoding = response.encoding or "utf-8"
        return response.text

    def _auth_headers(self, *, accept_only: bool = False) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.token}"}
        if accept_only:
            headers["Accept"] = "*/*"
        return headers

    def _prepare_artifact_dir(self, artifact_dir: str | Path | None) -> Path:
        path = Path(artifact_dir) if artifact_dir else Path.cwd() / "mineru_online_artifacts"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _find_precise_extract_result(self, payload: dict[str, Any], data_id: str) -> dict[str, Any]:
        data = payload.get("data") or {}
        results = data.get("extract_result") or []
        if isinstance(results, dict):
            return results
        for item in results:
            if item.get("data_id") == data_id:
                return item
        if results:
            return results[0]
        return {}

    def _find_first_file(self, directory: Path, patterns: list[str]) -> Path | None:
        for pattern in patterns:
            matches = sorted(directory.rglob(pattern))
            if matches:
                return matches[0]
        return None

    def _make_data_id(self, file_path: Path) -> str:
        safe_stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", file_path.stem).strip("._-")
        if not safe_stem:
            safe_stem = "document"
        return f"pdf2zh_{safe_stem}_{uuid.uuid4().hex[:8]}"[:128]

    def _normalize_agent_page_range(self, page_range: str | None) -> str | None:
        if not page_range:
            return None
        if "," in page_range:
            raise ValueError("MinerU Agent API only supports a single page or one continuous page range.")
        return page_range

    def _format_precise_state(self, state: str, progress: dict[str, Any]) -> str:
        if progress:
            current = progress.get("extracted_pages")
            total = progress.get("total_pages")
            if current is not None and total:
                return f"MinerU 精准解析中: {current}/{total} 页"
        labels = {
            "waiting-file": "等待文件上传",
            "pending": "排队中",
            "running": "解析中",
            "converting": "格式转换中",
        }
        return f"MinerU 精准 API 状态: {labels.get(state, state)}"

    def _emit(
        self,
        callback: ProgressCallback | None,
        progress: float,
        message: str,
        details: dict[str, Any] | None,
    ) -> None:
        logger.info(message)
        if callback:
            callback(progress, message, details)