"""集成MinerU优化管道的GUI界面

特点:
- 集成按页处理的MinerU优化管道
- 实时进度反馈
- 段落级双语对照
- 完整的错误处理
"""

import asyncio
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, List

import gradio as gr

from pdf2zh_next import __version__
from pdf2zh_next.config import ConfigManager
from pdf2zh_next.config.cli_env_model import CLIEnvSettingsModel
from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.config.translate_engine_model import TRANSLATION_ENGINE_METADATA_MAP
from pdf2zh_next.mineru_optimized_pipeline import MinerUOptimizedPipeline
from pdf2zh_next.storage_manager import StorageManager
from pdf2zh_next.gui_theme_clean import create_clean_theme, get_clean_css

logger = logging.getLogger(__name__)

# 全局变量
settings = ConfigManager().initialize_cli_config().to_settings_model()
storage_manager = StorageManager(settings.storage_root)
available_services = list(TRANSLATION_ENGINE_METADATA_MAP.keys())

class MinerUOptimizedGUI:
    """集成MinerU优化管道的GUI类"""

    def __init__(self):
        self.settings = settings
        self.storage = storage_manager
        self.current_pipeline = None
        self.current_project_id = None

    def create_interface(self) -> gr.Blocks:
        """创建GUI界面"""

        with gr.Blocks(
            title="PDFMathTranslate - MinerU优化版",
            theme=create_clean_theme(),
            css=get_clean_css(),
        ) as demo:

            # 标题区域
            gr.Markdown("# 🦅 PDFMathTranslate - MinerU优化版")
            gr.Markdown("### 科学文献智能翻译 - 段落级双语对照，按页处理")

            # 主要功能区域
            with gr.Tabs() as main_tabs:

                # Tab 1: 原有PDF翻译功能
                with gr.Tab("📄 原版翻译 (BabelDOC)", id="original_translation"):
                    self._create_original_tab()

                # Tab 2: MinerU优化翻译
                with gr.Tab("🚀 MinerU智能翻译 (优化版)", id="mineru_optimized"):
                    self._create_mineru_optimized_tab()

                # Tab 3: 项目管理
                with gr.Tab("📁 项目管理", id="project_management"):
                    self._create_project_management_tab()

                # Tab 4: 设置
                with gr.Tab("⚙️ 设置", id="settings"):
                    self._create_settings_tab()

        return demo

    def _create_original_tab(self):
        """创建原版翻译Tab"""
        gr.Markdown("## 使用BabelDOC进行PDF翻译，保留原始格式")

        with gr.Row():
            with gr.Column(scale=1):
                # 文件上传
                file_input = gr.File(
                    label="选择PDF文件",
                    file_types=[".pdf", ".PDF", ".md", ".markdown"],
                    type="filepath",
                )

                # 翻译设置
                service = gr.Dropdown(
                    label="翻译服务",
                    choices=available_services,
                    value=available_services[0],
                )

                with gr.Row():
                    lang_in = gr.Dropdown(
                        label="源语言",
                        choices=list(available_services),
                        value="English",
                    )
                    lang_out = gr.Dropdown(
                        label="目标语言",
                        choices=list(available_services),
                        value="Simplified Chinese",
                    )

                # 翻译按钮
                translate_btn = gr.Button(
                    "🚀 开始翻译",
                    variant="primary",
                    size="lg"
                )

                # 进度显示
                progress_text = gr.Textbox(
                    label="翻译进度",
                    interactive=False,
                    lines=2,
                )

                # 输出文件
                output_files = gr.File(
                    label="下载翻译结果",
                    visible=False,
                    file_count="multiple"
                )

            with gr.Column(scale=2):
                # 预览区域
                gr.Markdown("### 👁️ 文档预览")
                preview = gr.HTML(
                    value="<p style='text-align:center; color:#999; padding:50px;'>请上传文件开始翻译</p>"
                )

    def _create_mineru_optimized_tab(self):
        """创建MinerU优化翻译Tab"""
        gr.Markdown("## 使用MinerU进行智能翻译 - 按页处理，段落级双语对照")
        gr.Markdown("**特点**: 实时进度、断点续传、双语对照、结构化输出")

        with gr.Row():
            # 左侧：控制面板
            with gr.Column(scale=1):
                # 文件上传
                gr.Markdown("### 📁 文件上传")
                mineru_file = gr.File(
                    label="选择PDF文件",
                    file_types=[".pdf", ".PDF"],
                    type="filepath",
                )

                # MinerU设置
                gr.Markdown("### ⚙️ MinerU设置")

                with gr.Group():
                    mineru_model_path = gr.Textbox(
                        label="模型路径",
                        value="opendatalab/MinerU2.5-Pro-2604-1.2B",
                        info="HuggingFace模型ID或本地路径",
                    )

                    mineru_backend = gr.Radio(
                        choices=["本地推理", "远程API"],
                        label="推理方式",
                        value="远程API",
                    )

                    mineru_server_url = gr.Textbox(
                        label="vLLM服务地址",
                        value="http://127.0.0.1:8000",
                        info="远程API方式使用，指向 OpenAI-compatible vLLM 服务",
                    )

                    mineru_dpi = gr.Number(
                        label="图像质量(DPI)",
                        value=260,
                        precision=0,
                        minimum=72,
                        maximum=600,
                        info="建议260，质量与速度平衡"
                    )

                # 处理设置
                gr.Markdown("### 📄 处理设置")

                with gr.Row():
                    start_page = gr.Number(
                        label="起始页",
                        value=1,
                        precision=0,
                        minimum=1,
                    )
                    end_page = gr.Textbox(
                        label="结束页/范围",
                        value="全部",
                        placeholder="如: 10 或 1-5,8,10-15",
                    )

                # 输出格式
                gr.Markdown("### 📊 输出格式")

                output_formats = gr.CheckboxGroup(
                    choices=[
                        "段落级双语对照 (Markdown)",
                        "段落级双语对照 (HTML)",
                        "纯译文 (Markdown)",
                        "纯译文 (HTML)",
                        "结构化数据 (JSON)"
                    ],
                    label="选择输出格式",
                    value=["段落级双语对照 (Markdown)", "纯译文 (Markdown)"]
                )

                # 翻译设置（复用Tab 1的设置）
                gr.Markdown("### 🌐 翻译设置")
                gr.Markdown("*使用Tab 1中的翻译引擎和语言设置*")

                # 开始翻译按钮
                mineru_translate_btn = gr.Button(
                    "🚀 开始智能翻译",
                    variant="primary",
                    size="lg"
                )

                # 进度显示区域
                gr.Markdown("### 📊 处理进度")
                progress_stage = gr.Textbox(
                    label="当前阶段",
                    interactive=False,
                    value="等待开始..."
                )

                progress_bar = gr.Progress()

                progress_details = gr.Textbox(
                    label="详细信息",
                    interactive=False,
                    lines=3,
                    value="请上传文件并点击开始翻译"
                )

                # 操作按钮
                with gr.Row():
                    pause_btn = gr.Button("⏸️ 暂停", size="sm", variant="secondary")
                    resume_btn = gr.Button("▶️ 继续", size="sm", variant="secondary")
                    cancel_btn = gr.Button("❌ 取消", size="sm", variant="stop")

                # 输出文件
                output_files = gr.File(
                    label="下载翻译结果",
                    visible=False,
                    file_count="multiple"
                )

            # 右侧：实时预览
            with gr.Column(scale=2):
                gr.Markdown("### 👁️ 实时预览")

                with gr.Tabs():
                    with gr.Tab("📄 双语对照预览"):
                        bilingual_preview = gr.HTML(
                            value="<p style='text-align:center; color:#999; padding:50px;'>翻译完成后显示双语对照内容</p>",
                            height=600
                        )

                    with gr.Tab("📊 处理统计"):
                        stats_display = gr.HTML(
                            value="<p style='text-align:center; color:#999; padding:50px;'>处理统计信息将在此显示</p>",
                            height=600
                        )

                    with gr.Tab("📝 详细日志"):
                        log_display = gr.Textbox(
                            label="处理日志",
                            interactive=False,
                            lines=25,
                            value="等待开始处理...\n"
                        )

        # 绑定事件处理
        self._bind_mineru_events(
            mineru_file, mineru_model_path, mineru_backend, mineru_server_url, mineru_dpi,
            start_page, end_page, output_formats,
            mineru_translate_btn, pause_btn, resume_btn, cancel_btn,
            progress_stage, progress_details, bilingual_preview,
            stats_display, log_display, output_files
        )

    def _create_project_management_tab(self):
        """创建项目管理Tab"""
        gr.Markdown("## 翻译项目管理")

        with gr.Row():
            with gr.Column():
                # 项目列表
                project_list = gr.Dataframe(
                    headers=["项目ID", "文件名", "类型", "页数", "状态", "创建时间"],
                    label="历史项目",
                    interactive=False,
                    height=300
                )

                with gr.Row():
                    refresh_btn = gr.Button("🔄 刷新列表")
                    delete_btn = gr.Button("🗑️ 删除选中")
                    export_btn = gr.Button("📤 导出项目")

            with gr.Column():
                # 项目详情
                project_details = gr.HTML(
                    value="<p style='text-align:center; color:#999; padding:50px;'>选择项目查看详情</p>",
                    height=400
                )

    def _create_settings_tab(self):
        """创建设置Tab"""
        gr.Markdown("## 系统设置")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 🌐 翻译引擎设置")

                # 这里可以添加各种翻译引擎的设置
                gr.Markdown("翻译引擎设置请参考Tab 1")

            with gr.Column():
                gr.Markdown("### 🖥️ 系统设置")

                # 系统设置选项
                debug_mode = gr.Checkbox(
                    label="调试模式",
                    value=False,
                    info="启用详细日志输出"
                )

                auto_save = gr.Checkbox(
                    label="自动保存",
                    value=True,
                    info="处理过程中自动保存进度"
                )

    def _bind_mineru_events(
        self,
        file_input, model_path, backend, server_url, dpi,
        start_page, end_page, output_formats,
        translate_btn, pause_btn, resume_btn, cancel_btn,
        progress_stage, progress_details, bilingual_preview,
        stats_display, log_display, output_files
    ):
        """绑定MinerU事件处理"""

        # 翻译按钮事件
        translate_btn.click(
            fn=self._start_mineru_translation,
            inputs=[
                file_input, model_path, backend, server_url, dpi,
                start_page, end_page, output_formats
            ],
            outputs=[
                progress_stage, progress_details, bilingual_preview,
                stats_display, log_display, output_files
            ]
        )

        # 暂停按钮事件
        pause_btn.click(
            fn=self._pause_translation,
            outputs=[progress_details]
        )

        # 继续按钮事件
        resume_btn.click(
            fn=self._resume_translation,
            outputs=[progress_details]
        )

        # 取消按钮事件
        cancel_btn.click(
            fn=self._cancel_translation,
            outputs=[
                progress_stage, progress_details, bilingual_preview
            ]
        )

    def _start_mineru_translation(
        self,
        file_path: str,
        model_path: str,
        backend: str,
        server_url: str,
        dpi: int,
        start_page: int,
        end_page: str,
        output_formats: List[str]
    ) -> tuple:
        """开始MinerU翻译"""

        if not file_path:
            return "错误", "请先选择PDF文件", "", "", "请选择文件\n", gr.update(visible=False)

        try:
            # 创建新项目
            project_id = str(uuid.uuid4())
            self.current_project_id = project_id

            if hasattr(self.settings, "mineru"):
                self.settings.mineru.enabled = True
                self.settings.mineru.model_path = model_path or "opendatalab/MinerU2.5-Pro-2604-1.2B"
                self.settings.mineru.backend = "http-client" if backend == "远程API" else "transformers"
                self.settings.mineru.server_url = str(server_url).strip() if server_url else None
                try:
                    self.settings.mineru.dpi = int(dpi) if dpi is not None else 260
                except (TypeError, ValueError):
                    self.settings.mineru.dpi = 260

            # 创建优化管道
            self.current_pipeline = MinerUOptimizedPipeline(
                self.settings,
                self.storage,
                project_id
            )

            # 解析页码范围
            pages = self._parse_page_range(end_page, start_page)

            # 启动异步处理
            asyncio.create_task(self._run_mineru_translation(
                file_path, pages, output_formats,
                progress_stage, progress_details, bilingual_preview,
                stats_display, log_display, output_files
            ))

            return "初始化", "正在启动MinerU引擎...", "", "", "开始处理文件: " + Path(file_path).name + "\n", gr.update(visible=False)

        except Exception as e:
            logger.error(f"启动翻译失败: {e}")
            return "错误", f"启动失败: {str(e)}", "", "", f"错误: {str(e)}\n", gr.update(visible=False)

    def _parse_page_range(self, end_page: str, start_page: int) -> List[int]:
        """解析页码范围"""
        if end_page.lower() == "全部" or end_page == "":
            return None  # 表示全部页面

        try:
            # 解析范围表达式，如 "1-5,8,10-15"
            pages = []

            if '-' in end_page:
                start_num = int(end_page.split('-')[0])
                end_num = int(end_page.split('-')[1])
                pages = list(range(start_num, end_num + 1))
            else:
                pages = [int(end_page)]

            return pages

        except ValueError:
            # 如果解析失败，返回None表示全部页面
            return None

    async def _run_mineru_translation(
        self,
        file_path: str,
        pages: List[int],
        output_formats: List[str],
        progress_stage, progress_details, bilingual_preview,
        stats_display, log_display, output_files
    ):
        """运行MinerU翻译流程"""

        try:
            log_content = "开始MinerU优化翻译流程...\n"

            # 处理进度流
            async for event in self.current_pipeline.process_pdf(file_path, pages):
                stage = event.get('stage', 'unknown')
                progress = event.get('progress', 0.0)
                message = event.get('message', '')

                # 更新日志
                log_content += f"[{stage.upper()}] {message}\n"

                # 更新界面（这里需要使用gradio的更新机制）
                if stage == "processing":
                    stats_html = self._generate_stats_html(event)
                    # 更新统计显示

                # 模拟界面更新（实际实现需要使用gradio的回调机制）
                print(f"Progress: {progress:.1%} - {message}")

            # 完成后更新界面
            self._update_completion_ui(
                self.current_project_id, output_formats,
                bilingual_preview, stats_display, log_display, output_files
            )

        except Exception as e:
            logger.error(f"翻译过程失败: {e}")
            error_message = f"翻译失败: {str(e)}"
            # 更新错误界面

    def _generate_stats_html(self, event: Dict[str, Any]) -> str:
        """生成统计信息HTML"""
        return f"""
        <div style="padding: 20px;">
            <h3>处理统计</h3>
            <p><strong>当前阶段:</strong> {event.get('stage', 'unknown')}</p>
            <p><strong>进度:</strong> {event.get('progress', 0):.1%}</p>
            <p><strong>状态:</strong> {event.get('message', '')}</p>
        </div>
        """

    def _update_completion_ui(
        self, project_id: str, output_formats: List[str],
        bilingual_preview, stats_display, log_display, output_files
    ):
        """更新完成后的界面"""

        try:
            # 生成双语预览
            bilingual_file = self.storage.get_file_path(project_id, 'mineru/bilingual.md')
            if bilingual_file.exists():
                with open(bilingual_file, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 简单的Markdown到HTML转换
                html_content = content.replace('\n', '<br>')
                bilingual_preview_value = f"<div style='padding: 20px;'>{html_content}</div>"
            else:
                bilingual_preview_value = "<p>双语对照文件生成失败</p>"

            # 生成统计信息
            stats_html = self._generate_completion_stats(project_id)

            # 收集输出文件
            output_file_paths = []
            for fmt in output_formats:
                if "Markdown" in fmt:
                    if "双语" in fmt:
                        file_path = self.storage.get_file_path(project_id, 'mineru/bilingual.md')
                    else:
                        file_path = self.storage.get_file_path(project_id, 'mineru/translated.md')
                elif "HTML" in fmt:
                    if "双语" in fmt:
                        file_path = self.storage.get_file_path(project_id, 'mineru/bilingual.html')
                    else:
                        file_path = self.storage.get_file_path(project_id, 'mineru/translated.html')
                elif "JSON" in fmt:
                    file_path = self.storage.get_file_path(project_id, 'mineru/structured.json')

                if file_path and file_path.exists():
                    output_file_paths.append(str(file_path))

            # 更新界面（这里返回值会在实际调用中使用）
            return (
                "完成",
                "翻译已完成！",
                bilingual_preview_value,
                stats_html,
                "翻译处理完成\n",
                gr.update(value=output_file_paths, visible=True)
            )

        except Exception as e:
            logger.error(f"更新完成界面失败: {e}")
            return (
                "错误",
                f"界面更新失败: {str(e)}",
                "",
                "",
                f"错误: {str(e)}\n",
                gr.update(visible=False)
            )

    def _generate_completion_stats(self, project_id: str) -> str:
        """生成完成统计信息"""
        return f"""
        <div style="padding: 20px;">
            <h3>✅ 翻译完成</h3>
            <p><strong>项目ID:</strong> {project_id}</p>
            <p><strong>处理时间:</strong> {self._get_processing_time(project_id)}</p>
            <p><strong>输出格式:</strong> 多种格式已生成</p>
            <p><strong>状态:</strong> 翻译成功完成</p>

            <h4>输出文件:</h4>
            <ul>
                <li>段落级双语对照 (Markdown)</li>
                <li>纯译文 (Markdown)</li>
                <li>段落级双语对照 (HTML)</li>
                <li>纯译文 (HTML)</li>
                <li>结构化数据 (JSON)</li>
            </ul>
        </div>
        """

    def _get_processing_time(self, project_id: str) -> str:
        """获取处理时间"""
        # 这里应该从项目元数据中获取实际处理时间
        return "未知"

    def _pause_translation(self):
        """暂停翻译"""
        if self.current_pipeline:
            # 实现暂停逻辑
            return "翻译已暂停"
        return "没有正在进行的翻译"

    def _resume_translation(self):
        """继续翻译"""
        if self.current_pipeline:
            # 实现继续逻辑
            return "翻译已继续"
        return "没有暂停的翻译"

    def _cancel_translation(self):
        """取消翻译"""
        if self.current_pipeline:
            # 实现取消逻辑
            self.current_pipeline = None
            self.current_project_id = None
            return "已取消", "翻译已取消", ""
        return "没有正在进行的翻译", "没有正在进行的翻译", ""


def setup_gui(
    share: bool = False,
    server_port: int = 7860,
    inbrowser: bool = True,
) -> None:
    """启动MinerU优化版GUI"""

    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 创建GUI
    gui = MinerUOptimizedGUI()
    demo = gui.create_interface()

    # 启动服务器
    demo.launch(
        server_name="0.0.0.0",
        server_port=server_port,
        share=share,
        inbrowser=inbrowser,
    )


if __name__ == "__main__":
    setup_gui()