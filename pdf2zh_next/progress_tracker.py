"""实时进度跟踪器 - 支持MinerU翻译流程的实时反馈"""

import asyncio
import logging
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Callable, AsyncGenerator
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    """处理阶段枚举"""

    INIT = "init"
    LOADING = "loading"
    EXTRACTION = "extraction"
    TRANSLATION = "translation"
    FORMATTING = "formatting"
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class ProgressEvent:
    """进度事件数据"""

    stage: ProcessingStage
    progress: float  # 0.0 - 1.0
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    page_num: Optional[int] = None
    total_pages: Optional[int] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["stage"] = self.stage.value
        data["timestamp"] = self.timestamp.isoformat()
        return data


class ProgressTracker:
    """实时进度跟踪器"""

    def __init__(self, total_pages: Optional[int] = None):
        """初始化进度跟踪器

        Args:
            total_pages: 总页数，用于计算进度
        """
        self.total_pages = total_pages
        self.current_page = 0
        self.start_time = datetime.now()
        self.last_update_time = None

        # 状态管理
        self._is_paused = False
        self._is_cancelled = False
        self._current_stage = ProcessingStage.INIT

        # 进度回调函数
        self._progress_callbacks: List[Callable[[ProgressEvent], None]] = []

        # 统计信息
        self._stage_start_times: Dict[ProcessingStage, datetime] = {}
        self._completed_pages = 0
        self._failed_pages = 0
        self._processing_times: List[float] = []

        logger.info(f"进度跟踪器初始化，总页数: {total_pages}")

    def add_progress_callback(self, callback: Callable[[ProgressEvent], None]):
        """添加进度回调函数"""
        self._progress_callbacks.append(callback)
        logger.debug(f"添加进度回调，当前回调数量: {len(self._progress_callbacks)}")

    def remove_progress_callback(self, callback: Callable[[ProgressEvent], None]):
        """移除进度回调函数"""
        if callback in self._progress_callbacks:
            self._progress_callbacks.remove(callback)
            logger.debug(f"移除进度回调，当前回调数量: {len(self._progress_callbacks)}")

    def _notify_progress(self, event: ProgressEvent):
        """通知所有回调函数"""
        if not self._is_cancelled:
            for callback in self._progress_callbacks:
                try:
                    callback(event)
                except Exception as e:
                    logger.error(f"进度回调函数执行失败: {e}")

    def update_stage(
        self,
        stage: ProcessingStage,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """更新处理阶段"""
        self._current_stage = stage
        self._stage_start_times[stage] = datetime.now()

        progress = self._calculate_stage_progress(stage)

        event = ProgressEvent(
            stage=stage,
            progress=progress,
            message=message,
            details=details,
            total_pages=self.total_pages,
        )

        logger.info(f"阶段更新: {stage.value} - {message}")
        self._notify_progress(event)
        self.last_update_time = datetime.now()

    def update_page_progress(
        self,
        page_num: int,
        total_pages: int,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        """更新页面处理进度"""
        self.current_page = page_num
        self.total_pages = total_pages

        # 计算进度
        progress = (page_num - 1) / total_pages if total_pages > 0 else 0.0

        event = ProgressEvent(
            stage=self._current_stage,
            progress=progress,
            message=message,
            details=details,
            page_num=page_num,
            total_pages=total_pages,
        )

        logger.debug(f"页面进度: {page_num}/{total_pages} - {message}")
        self._notify_progress(event)
        self.last_update_time = datetime.now()

    def update_extraction_progress(
        self, page_num: int, total_pages: int, blocks_found: int, message: str
    ):
        """更新提取进度"""
        details = {
            "blocks_found": blocks_found,
            "extraction_rate": blocks_found / 10.0,  # 假设平均每页10个blocks
        }

        self.update_page_progress(page_num, total_pages, message, details)

    def update_translation_progress(
        self,
        page_num: int,
        total_pages: int,
        blocks_translated: int,
        total_blocks: int,
        message: str,
    ):
        """更新翻译进度"""
        # 翻译阶段通常占总进度的50%
        page_progress = (page_num - 1) / total_pages if total_pages > 0 else 0.0
        block_progress = blocks_translated / total_blocks if total_blocks > 0 else 0.0
        overall_progress = (
            0.3 + page_progress * 0.5 + block_progress * 0.2
        )  # 提取30% + 翻译50% + 格式化20%

        details = {
            "blocks_translated": blocks_translated,
            "total_blocks": total_blocks,
            "translation_rate": block_progress,
        }

        event = ProgressEvent(
            stage=ProcessingStage.TRANSLATION,
            progress=min(overall_progress, 0.9),  # 翻译阶段最高到90%
            message=message,
            details=details,
            page_num=page_num,
            total_pages=total_pages,
        )

        logger.debug(
            f"翻译进度: {page_num}/{total_pages}, {blocks_translated}/{total_blocks} blocks"
        )
        self._notify_progress(event)
        self.last_update_time = datetime.now()

    def mark_page_completed(self, page_num: int, processing_time: float):
        """标记页面完成"""
        self._completed_pages += 1
        self._processing_times.append(processing_time)

        # 计算平均处理时间
        avg_time = (
            sum(self._processing_times) / len(self._processing_times)
            if self._processing_times
            else 0
        )

        # 估算剩余时间
        remaining_pages = (
            self.total_pages - self._completed_pages if self.total_pages else 0
        )
        eta_seconds = remaining_pages * avg_time

        details = {
            "completed_pages": self._completed_pages,
            "failed_pages": self._failed_pages,
            "avg_processing_time": avg_time,
            "eta_seconds": eta_seconds,
            "eta_formatted": self._format_time(eta_seconds),
        }

        event = ProgressEvent(
            stage=self._current_stage,
            progress=self._calculate_overall_progress(),
            message=f"第 {page_num} 页完成",
            details=details,
            page_num=page_num,
            total_pages=self.total_pages,
        )

        self._notify_progress(event)

    def mark_page_failed(self, page_num: int, error: str):
        """标记页面失败"""
        self._failed_pages += 1
        logger.warning(f"第 {page_num} 页处理失败: {error}")

    def pause(self):
        """暂停处理"""
        self._is_paused = True

        event = ProgressEvent(
            stage=ProcessingStage.PAUSED,
            progress=self._calculate_overall_progress(),
            message="处理已暂停",
        )

        self._notify_progress(event)
        logger.info("处理已暂停")

    def resume(self):
        """恢复处理"""
        self._is_paused = False

        event = ProgressEvent(
            stage=self._current_stage,
            progress=self._calculate_overall_progress(),
            message="处理已恢复",
        )

        self._notify_progress(event)
        logger.info("处理已恢复")

    def cancel(self):
        """取消处理"""
        self._is_cancelled = True

        event = ProgressEvent(
            stage=ProcessingStage.CANCELLED,
            progress=self._calculate_overall_progress(),
            message="处理已取消",
        )

        self._notify_progress(event)
        logger.info("处理已取消")

    def complete(self, message: str = "处理完成"):
        """标记处理完成"""
        total_time = (datetime.now() - self.start_time).total_seconds()

        details = {
            "total_time": total_time,
            "formatted_time": self._format_time(total_time),
            "completed_pages": self._completed_pages,
            "failed_pages": self._failed_pages,
            "success_rate": self._completed_pages
            / (self._completed_pages + self._failed_pages)
            if (self._completed_pages + self._failed_pages) > 0
            else 0,
            "avg_processing_time": sum(self._processing_times)
            / len(self._processing_times)
            if self._processing_times
            else 0,
        }

        event = ProgressEvent(
            stage=ProcessingStage.COMPLETED,
            progress=1.0,
            message=message,
            details=details,
            total_pages=self.total_pages,
        )

        self._notify_progress(event)
        logger.info(f"处理完成: {message}, 耗时: {total_time:.2f}秒")

    def error(self, message: str, details: Optional[Dict[str, Any]] = None):
        """标记错误"""
        event = ProgressEvent(
            stage=ProcessingStage.ERROR,
            progress=self._calculate_overall_progress(),
            message=f"错误: {message}",
            details=details,
        )

        self._notify_progress(event)
        logger.error(f"处理错误: {message}")

    def _calculate_stage_progress(self, stage: ProcessingStage) -> float:
        """计算阶段进度"""
        stage_progress_map = {
            ProcessingStage.INIT: 0.0,
            ProcessingStage.LOADING: 0.1,
            ProcessingStage.EXTRACTION: 0.3,
            ProcessingStage.TRANSLATION: 0.8,
            ProcessingStage.FORMATTING: 0.95,
            ProcessingStage.COMPLETED: 1.0,
        }
        return stage_progress_map.get(stage, 0.0)

    def _calculate_overall_progress(self) -> float:
        """计算总体进度"""
        if self.total_pages and self.total_pages > 0:
            # 基于页面数的进度计算
            base_progress = (
                self._completed_pages / self.total_pages
            ) * 0.9  # 页面处理占90%
            stage_progress = self._calculate_stage_progress(self._current_stage)
            return min(base_progress + stage_progress * 0.1, 1.0)
        else:
            # 基于阶段的进度计算
            return self._calculate_stage_progress(self._current_stage)

    def _format_time(self, seconds: float) -> str:
        """格式化时间显示"""
        if seconds < 60:
            return f"{seconds:.1f}秒"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}分{secs}秒"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}小时{minutes}分钟"

    def is_paused(self) -> bool:
        """检查是否暂停"""
        return self._is_paused

    def is_cancelled(self) -> bool:
        """检查是否取消"""
        return self._is_cancelled

    def get_status(self) -> Dict[str, Any]:
        """获取当前状态"""
        return {
            "stage": self._current_stage.value,
            "progress": self._calculate_overall_progress(),
            "current_page": self.current_page,
            "total_pages": self.total_pages,
            "completed_pages": self._completed_pages,
            "failed_pages": self._failed_pages,
            "is_paused": self._is_paused,
            "is_cancelled": self._is_cancelled,
            "start_time": self.start_time.isoformat(),
            "last_update": self.last_update_time.isoformat()
            if self.last_update_time
            else None,
            "elapsed_time": (datetime.now() - self.start_time).total_seconds(),
        }


class AsyncProgressTracker:
    """异步进度跟踪器 - 支持异步生成器"""

    def __init__(self, total_pages: Optional[int] = None):
        """初始化异步进度跟踪器"""
        self.tracker = ProgressTracker(total_pages)
        self._event_queue = asyncio.Queue()
        self._consumer_task = None
        self._is_running = False
        self._last_event: ProgressEvent | None = None

    async def start(self):
        """启动异步消费"""
        if not self._is_running:
            self._is_running = True
            if self.tracker._progress_callbacks:
                self._consumer_task = asyncio.create_task(self._consume_events())
            logger.debug("异步进度跟踪器已启动")

    async def stop(self):
        """停止异步消费"""
        self._is_running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        logger.debug("异步进度跟踪器已停止")

    async def _consume_events(self):
        """消费事件队列"""
        while self._is_running:
            try:
                event = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                self.tracker._notify_progress(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"消费进度事件失败: {e}")

    def put_event(self, event: ProgressEvent):
        """放入事件"""
        try:
            self._last_event = event
            self.tracker._current_stage = event.stage
            if event.total_pages is not None:
                self.tracker.total_pages = event.total_pages
            if event.page_num is not None:
                self.tracker.current_page = event.page_num
            self.tracker.last_update_time = datetime.now()
            self._event_queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("进度事件队列已满，丢弃事件")

    async def progress_stream(self) -> AsyncGenerator[Dict[str, Any], None]:
        """生成进度流"""
        await self.start()

        try:
            last_progress = -1.0

            while self._is_running or not self._event_queue.empty():
                # 检查状态变化
                current_status = self.tracker.get_status()
                current_progress = current_status["progress"]

                # 只有进度变化时才发送
                if abs(current_progress - last_progress) >= 0.01:  # 1%的变化
                    yield {
                        "stage": current_status["stage"],
                        "progress": current_progress,
                        "message": self._get_current_message(),
                        "details": current_status,
                        "timestamp": datetime.now().isoformat(),
                    }
                    last_progress = current_progress

                await asyncio.sleep(0.5)  # 每500ms检查一次

        finally:
            await self.stop()

    def _get_current_message(self) -> str:
        """获取当前消息"""
        if self._last_event is not None and self._last_event.message:
            return self._last_event.message
        if self.tracker._is_paused:
            return "处理已暂停"
        elif self.tracker._is_cancelled:
            return "处理已取消"
        elif self.tracker._current_stage == ProcessingStage.INIT:
            return "正在初始化..."
        elif self.tracker._current_stage == ProcessingStage.LOADING:
            return "正在加载模型..."
        elif self.tracker._current_stage == ProcessingStage.EXTRACTION:
            if self.tracker.current_page and self.tracker.total_pages:
                return f"正在识别第 {self.tracker.current_page}/{self.tracker.total_pages} 页..."
            return "正在识别文档结构..."
        elif self.tracker._current_stage == ProcessingStage.TRANSLATION:
            if self.tracker.current_page and self.tracker.total_pages:
                return f"正在翻译第 {self.tracker.current_page}/{self.tracker.total_pages} 页..."
            return "正在翻译内容..."
        elif self.tracker._current_stage == ProcessingStage.FORMATTING:
            return "正在生成输出文件..."
        elif self.tracker._current_stage == ProcessingStage.COMPLETED:
            return "处理完成！"
        elif self.tracker._current_stage == ProcessingStage.ERROR:
            return "处理过程中出现错误"
        else:
            return "正在处理..."

    # 代理方法到内部tracker
    def add_progress_callback(self, callback: Callable[[ProgressEvent], None]):
        self.tracker.add_progress_callback(callback)

    def remove_progress_callback(self, callback: Callable[[ProgressEvent], None]):
        self.tracker.remove_progress_callback(callback)

    def update_stage(
        self,
        stage: ProcessingStage,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.tracker._current_stage = stage
        self.tracker._stage_start_times[stage] = datetime.now()
        self.tracker.last_update_time = datetime.now()
        event = ProgressEvent(
            stage=stage,
            progress=self.tracker._calculate_stage_progress(stage),
            message=message,
            details=details,
            total_pages=self.tracker.total_pages,
        )
        self.put_event(event)

    def update_page_progress(
        self,
        page_num: int,
        total_pages: int,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.tracker.current_page = page_num
        self.tracker.total_pages = total_pages
        self.tracker.last_update_time = datetime.now()
        event = ProgressEvent(
            stage=self.tracker._current_stage,
            progress=(page_num - 1) / total_pages if total_pages > 0 else 0.0,
            message=message,
            details=details,
            page_num=page_num,
            total_pages=total_pages,
        )
        self.put_event(event)

    def update_extraction_progress(
        self, page_num: int, total_pages: int, blocks_found: int, message: str
    ):
        details = {
            "blocks_found": blocks_found,
            "extraction_rate": blocks_found / 10.0,
        }
        self.update_page_progress(page_num, total_pages, message, details)

    def update_translation_progress(
        self,
        page_num: int,
        total_pages: int,
        blocks_translated: int,
        total_blocks: int,
        message: str,
    ):
        block_progress = blocks_translated / total_blocks if total_blocks > 0 else 0.0
        details = {
            "blocks_translated": blocks_translated,
            "total_blocks": total_blocks,
            "translation_rate": block_progress,
        }
        self.update_page_progress(page_num, total_pages, message, details)

    def mark_page_completed(self, page_num: int, processing_time: float):
        self.tracker.mark_page_completed(page_num, processing_time)

    def mark_page_failed(self, page_num: int, error: str):
        self.tracker.mark_page_failed(page_num, error)

    def complete(self, message: str = "处理完成"):
        self.tracker.complete(message)
        event = ProgressEvent(
            stage=ProcessingStage.COMPLETED, progress=1.0, message=message
        )
        self.put_event(event)

    def error(self, message: str, details: Optional[Dict[str, Any]] = None):
        self.tracker.error(message, details)
        event = ProgressEvent(
            stage=ProcessingStage.ERROR,
            progress=0.0,
            message=f"错误: {message}",
            details=details,
        )
        self.put_event(event)

    def pause(self):
        self.tracker.pause()

    def resume(self):
        self.tracker.resume()

    def cancel(self):
        self.tracker.cancel()
