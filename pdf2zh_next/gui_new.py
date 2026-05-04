"""新UI主界面 - 基于Gradio的现代化用户界面

参考reference-them的设计风格，提供:
- Hero区域 - 欢迎页面
- 翻译界面 - 上传PDF，选择格式，执行翻译
- 项目管理 - 查看历史项目
- 文档浏览 - 预览翻译结果
- 设置页面 - 配置翻译引擎和MinerU
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Optional

import gradio as gr

from pdf2zh_next.config import ConfigManager
from pdf2zh_next.config.cli_env_model import CLIEnvSettingsModel
from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.document_viewer import DocumentViewer
from pdf2zh_next.high_level import do_translate_async_stream
from pdf2zh_next.gui_theme import create_custom_theme, get_custom_css
from pdf2zh_next.storage_manager import StorageManager
from pdf2zh_next.config.translate_engine_model import (
    TRANSLATION_ENGINE_METADATA,
    TRANSLATION_ENGINE_METADATA_MAP,
    GUI_SENSITIVE_FIELDS,
    GUI_PASSWORD_FIELDS,
)

logger = logging.getLogger(__name__)


class PDFTranslateUI:
    """PDF翻译UI主类"""

    def __init__(self, settings: Optional[CLIEnvSettingsModel] = None):
        """初始化UI

        Args:
            settings: 应用配置，None则使用默认配置
        """
        # 使用CLIEnvSettingsModel，如果没有提供则从配置管理器加载
        # 持久化配置管理器（用于写回用户默认配置）
        self.config_manager = ConfigManager()
        if settings is None:
            try:
                self.cli_settings = self.config_manager.initialize_cli_config()
            except Exception as e:
                logger.warning(f"无法加载配置: {e}，使用默认配置")
                self.cli_settings = CLIEnvSettingsModel()
        else:
            self.cli_settings = settings

        # 转换为SettingsModel用于内部使用
        self.settings = self.cli_settings.to_settings_model()

        # 初始化组件
        self.storage = StorageManager(self.settings.storage_root)
        self.viewer = DocumentViewer(max_pdf_pages=10)

        # UI状态
        self.current_project_id = None

        logger.info("PDF翻译UI初始化完成")
    
    def create_ui(self) -> gr.Blocks:
        """创建Gradio UI
        
        Returns:
            Gradio Blocks对象
        """
        # 创建自定义主题
        theme = create_custom_theme()
        custom_css = get_custom_css()
        
        with gr.Blocks(
            theme=theme,
            css=custom_css,
            title="PDFMathTranslate - 科学文档翻译工具"
        ) as app:
            # Hero区域
            self._create_hero_section()
            
            # 主要功能区域
            with gr.Tabs() as tabs:
                # Tab 1: 翻译界面
                with gr.Tab("📄 翻译文档", id="translate"):
                    self._create_translation_tab()
                
                # Tab 2: 项目管理
                with gr.Tab("📁 项目管理", id="projects"):
                    self._create_projects_tab()
                
                # Tab 3: 文档浏览
                with gr.Tab("👁️ 文档浏览", id="viewer"):
                    self._create_viewer_tab()
                
                # Tab 4: 设置
                with gr.Tab("⚙️ 设置", id="settings"):
                    self._create_settings_tab()
        
        return app
    
    def _create_hero_section(self):
        """创建Hero区域"""
        with gr.Row(elem_classes="hero-section"):
            with gr.Column():
                gr.Markdown(
                    """
                    # <span class="gradient-text">PDFMathTranslate</span>
                    
                    ### 专业的科学文档翻译工具
                    
                    保留公式、图表、表格，支持多种翻译引擎，输出PDF、Markdown、HTML等多种格式
                    """,
                    elem_classes="hero-title"
                )
                
                with gr.Row():
                    gr.Markdown(
                        """
                        <div class="feature-card">
                            <h3>🎯 精确翻译</h3>
                            <p>保持原文格式，精确翻译科学文档</p>
                        </div>
                        """,
                        elem_classes="feature-card-wrapper"
                    )
                    gr.Markdown(
                        """
                        <div class="feature-card">
                            <h3>🚀 多种引擎</h3>
                            <p>支持20+翻译服务，灵活选择</p>
                        </div>
                        """,
                        elem_classes="feature-card-wrapper"
                    )
                    gr.Markdown(
                        """
                        <div class="feature-card">
                            <h3>📊 多格式输出</h3>
                            <p>PDF、Markdown、HTML，满足不同需求</p>
                        </div>
                        """,
                        elem_classes="feature-card-wrapper"
                    )
    
    def _create_translation_tab(self):
        """创建翻译界面Tab"""
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📤 上传文档")
                
                # 文件上传
                pdf_input = gr.File(
                    label="选择PDF文件",
                    file_types=[".pdf"],
                    type="filepath"
                )
                
                # 文档信息
                doc_title = gr.Textbox(
                    label="文档标题",
                    placeholder="自动从文件名提取",
                    interactive=True
                )
                
                gr.Markdown("### 🎨 翻译选项")
                
                # 翻译路径选择
                translation_path = gr.Radio(
                    choices=[
                        ("PDF格式 (保持原格式)", "babeldoc"),
                        ("Markdown/HTML (结构化输出)", "mineru")
                    ],
                    value="babeldoc",
                    label="翻译路径",
                    info="选择不同的翻译方式"
                )
                
                # 输出格式选择（仅MinerU路径）
                output_formats = gr.CheckboxGroup(
                    choices=["Markdown", "HTML"],
                    value=["Markdown", "HTML"],
                    label="输出格式 (MinerU路径)",
                    visible=False
                )
                
                # 语言选择
                with gr.Row():
                    lang_in = gr.Dropdown(
                        choices=["en", "zh", "ja", "ko", "fr", "de", "es", "ru"],
                        value="en",
                        label="源语言"
                    )
                    lang_out = gr.Dropdown(
                        choices=["zh", "en", "ja", "ko", "fr", "de", "es", "ru"],
                        value="zh",
                        label="目标语言"
                    )
                
                # 翻译按钮
                translate_btn = gr.Button(
                    "🚀 开始翻译",
                    variant="primary",
                    size="lg",
                    elem_classes="translate-button"
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 📊 翻译进度")
                
                # 进度显示
                progress_bar = gr.Progress()
                status_text = gr.Textbox(
                    label="状态",
                    value="等待上传文件...",
                    interactive=False,
                    lines=3
                )
                
                # 进度详情
                progress_details = gr.JSON(
                    label="详细信息",
                    visible=False
                )
                
                gr.Markdown("### 📥 翻译结果")
                
                # 结果显示
                result_files = gr.File(
                    label="下载文件",
                    file_count="multiple",
                    interactive=False
                )
                
                # 项目ID（隐藏）
                project_id_state = gr.State()
        
        # 事件处理
        
        # 翻译路径改变时，显示/隐藏输出格式选项
        def on_path_change(path):
            return gr.update(visible=(path == "mineru"))
        
        translation_path.change(
            fn=on_path_change,
            inputs=[translation_path],
            outputs=[output_formats]
        )
        
        # 文件上传时，自动提取标题
        def on_file_upload(file_path):
            if file_path:
                title = Path(file_path).stem
                return title
            return ""
        
        pdf_input.change(
            fn=on_file_upload,
            inputs=[pdf_input],
            outputs=[doc_title]
        )
        
        # 翻译按钮点击
        translate_btn.click(
            fn=self._handle_translation,
            inputs=[
                pdf_input,
                doc_title,
                translation_path,
                output_formats,
                lang_in,
                lang_out
            ],
            outputs=[
                status_text,
                progress_details,
                result_files,
                project_id_state
            ]
        )
    
    def _create_projects_tab(self):
        """创建项目管理Tab"""
        with gr.Row():
            with gr.Column(scale=2):
                gr.Markdown("### 📁 项目列表")
                
                # 刷新按钮
                refresh_btn = gr.Button("🔄 刷新", size="sm")
                
                # 项目列表
                projects_list = gr.Dataframe(
                    headers=["项目ID", "标题", "状态", "创建时间", "翻译路径"],
                    datatype=["str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True
                )
                
                # 加载项目列表
                def load_projects():
                    projects = self.storage.list_projects(sort_by="created_at")
                    
                    data = []
                    for proj in projects:
                        data.append([
                            proj['project_id'],
                            proj.get('title', 'Untitled'),
                            proj.get('status', 'unknown'),
                            proj.get('created_at', ''),
                            proj.get('translation_path', 'babeldoc')
                        ])
                    
                    return data
                
                # 初始加载
                projects_list.value = load_projects()
                
                # 刷新按钮
                refresh_btn.click(
                    fn=load_projects,
                    outputs=[projects_list]
                )
            
            with gr.Column(scale=1):
                gr.Markdown("### 📋 项目详情")
                
                # 选择的项目ID
                selected_project_id = gr.Textbox(
                    label="项目ID",
                    placeholder="从列表中选择项目",
                    interactive=True
                )
                
                # 项目信息
                project_info = gr.JSON(label="项目信息")
                
                # 查看按钮
                view_btn = gr.Button("👁️ 查看文件", variant="secondary")
                
                # 删除按钮
                delete_btn = gr.Button("🗑️ 删除项目", variant="stop")
                
                # 查看项目详情
                def view_project(project_id):
                    if not project_id:
                        return None
                    
                    try:
                        project = self.storage.get_project(project_id)
                        return project
                    except Exception as e:
                        logger.error(f"获取项目失败: {e}")
                        return {"error": str(e)}
                
                selected_project_id.change(
                    fn=view_project,
                    inputs=[selected_project_id],
                    outputs=[project_info]
                )
                
                # 删除项目
                def delete_project(project_id):
                    if not project_id:
                        return "请输入项目ID", load_projects()
                    
                    try:
                        self.storage.delete_project(project_id)
                        return f"项目 {project_id} 已删除", load_projects()
                    except Exception as e:
                        logger.error(f"删除项目失败: {e}")
                        return f"删除失败: {e}", load_projects()
                
                delete_btn.click(
                    fn=delete_project,
                    inputs=[selected_project_id],
                    outputs=[project_info, projects_list]
                )
    
    def _create_viewer_tab(self):
        """创建文档浏览Tab"""
        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 📂 选择文件")
                
                # 项目ID输入
                viewer_project_id = gr.Textbox(
                    label="项目ID",
                    placeholder="输入项目ID"
                )
                
                # 文件列表
                file_list = gr.Radio(
                    label="选择文件",
                    choices=[],
                    interactive=True
                )
                
                # 加载文件列表
                def load_files(project_id):
                    if not project_id:
                        return gr.update(choices=[])
                    
                    try:
                        project = self.storage.get_project(project_id)
                        files = []
                        
                        # 添加源文件
                        files.append(("源文件: source.pdf", "source.pdf"))
                        
                        # 添加结果文件
                        for path_type, file_list in project.get('results', {}).items():
                            for file_name in file_list:
                                files.append((f"{path_type}: {file_name}", f"{path_type}/{file_name}"))
                        
                        return gr.update(choices=files)
                    except Exception as e:
                        logger.error(f"加载文件列表失败: {e}")
                        return gr.update(choices=[])
                
                viewer_project_id.change(
                    fn=load_files,
                    inputs=[viewer_project_id],
                    outputs=[file_list]
                )
            
            with gr.Column(scale=2):
                gr.Markdown("### 👁️ 文件预览")
                
                # HTML预览
                html_preview = gr.HTML(label="预览")
                
                # 图片预览（用于PDF）
                image_preview = gr.Gallery(
                    label="PDF预览",
                    visible=False,
                    columns=1,
                    height="auto"
                )
                
                # 预览文件
                def preview_file(project_id, file_path):
                    if not project_id or not file_path:
                        return "<p>请选择文件</p>", [], gr.update(visible=False)
                    
                    try:
                        full_path = self.storage.get_file_path(project_id, file_path)
                        
                        if not full_path.exists():
                            return f"<p>文件不存在: {file_path}</p>", [], gr.update(visible=False)
                        
                        # 渲染文件
                        html_content, images = self.viewer.render_file(full_path)
                        
                        if images:
                            # PDF文件，显示图片
                            return "", images, gr.update(visible=True)
                        else:
                            # 其他文件，显示HTML
                            return html_content, [], gr.update(visible=False)
                    
                    except Exception as e:
                        logger.error(f"预览文件失败: {e}", exc_info=True)
                        return f"<p>预览失败: {e}</p>", [], gr.update(visible=False)
                
                file_list.change(
                    fn=preview_file,
                    inputs=[viewer_project_id, file_list],
                    outputs=[html_preview, image_preview, image_preview]
                )
    
    def _create_settings_tab(self):
        """创建设置Tab（复刻 BabelDOC 原应用的可交互设置）"""

        # 计算当前启用的服务列表
        available_services = [x.translate_engine_type for x in TRANSLATION_ENGINE_METADATA]
        enabled_services_cfg = getattr(self.cli_settings.gui_settings, "enabled_services", None)
        if enabled_services_cfg:
            enabled_services = {x.strip().lower() for x in enabled_services_cfg.split(",") if x.strip()}
            available_services = [x for x in available_services if x.lower() in enabled_services]
        assert available_services, "没有可用的翻译服务"

        # 识别当前选中的服务（根据 CLI 标志位）
        selected_service = None
        for meta in TRANSLATION_ENGINE_METADATA:
            if getattr(self.cli_settings, meta.cli_flag_name, False):
                selected_service = meta.translate_engine_type
                break
        if selected_service is None:
            selected_service = available_services[0]

        disable_sensitive_input = getattr(self.cli_settings.gui_settings, "disable_gui_sensitive_input", False)

        gr.Markdown("### ⚙️ 翻译引擎设置")
        gr.Markdown("选择服务并填写对应参数，点击保存后将写入应用配置，供后续翻译使用。")

        detail_text_inputs = []
        detail_text_input_index_map = {}
        service_arg_names_map = {}

        with gr.Group():
            service_dd = gr.Dropdown(
                label="翻译服务",
                choices=available_services,
                value=selected_service,
            )

            # 为每个服务创建对应参数输入（仅展示当前选中的服务，其他隐藏）
            detail_index = 0
            for service_name in available_services:
                meta = TRANSLATION_ENGINE_METADATA_MAP[service_name]
                # 若无详细字段，跳过
                if not meta.cli_detail_field_name:
                    continue
                detail_settings = getattr(self.cli_settings, meta.cli_detail_field_name)
                # 记录当前服务的索引映射
                detail_text_input_index_map[meta.translate_engine_type] = []
                service_arg_names_map[meta.translate_engine_type] = []

                visible = service_name == selected_service
                with gr.Group(visible=visible):
                    for field_name, field in meta.setting_model_type.model_fields.items():
                        # 跳过内部字段与默认工厂字段
                        if field.default_factory:
                            continue
                        if field_name in ("translate_engine_type", "support_llm"):
                            continue
                        # 根据敏感字段配置隐藏
                        if disable_sensitive_input and (field_name in GUI_SENSITIVE_FIELDS or field_name in GUI_PASSWORD_FIELDS):
                            continue

                        type_hint = field.annotation
                        current_val = getattr(detail_settings, field_name)

                        # 根据类型创建输入组件
                        if type_hint is str:
                            inp = gr.Textbox(label=field_name, value=current_val or "", interactive=True, visible=visible)
                        elif type_hint is int:
                            inp = gr.Number(label=field_name, value=int(current_val or 0), precision=0, interactive=True, visible=visible)
                        elif type_hint is bool:
                            inp = gr.Checkbox(label=field_name, value=bool(current_val), interactive=True, visible=visible)
                        else:
                            # 简化实现：其他复杂类型暂不支持在设置页编辑
                            inp = gr.Textbox(label=f"{field_name} (未完全支持类型)", value=str(current_val) if current_val is not None else "", interactive=True, visible=visible)

                        detail_text_inputs.append(inp)
                        detail_text_input_index_map[meta.translate_engine_type].append(detail_index)
                        service_arg_names_map[meta.translate_engine_type].append(field_name)
                        detail_index += 1

            # 切换服务时更新参数输入的可见性
            def on_select_service(service_name: str):
                if not detail_text_inputs:
                    return []
                idxs = detail_text_input_index_map.get(service_name, [])
                updates = []
                total = len(detail_text_inputs)
                if total == 0:
                    return []
                for i in range(total):
                    updates.append(gr.update(visible=(i in idxs)))
                return updates

            service_dd.change(
                fn=on_select_service,
                inputs=[service_dd],
                outputs=detail_text_inputs if detail_text_inputs else [],
            )

        # 保存按钮与状态
        save_status = gr.Markdown(visible=False)
        save_btn = gr.Button("💾 保存设置", variant="primary")

        def apply_engine_settings(service_name: str, *all_args):
            try:
                # 1) 清除所有引擎标志位
                for meta in TRANSLATION_ENGINE_METADATA:
                    setattr(self.cli_settings, meta.cli_flag_name, False)

                # 2) 设置当前选中引擎标志位
                chosen_meta = TRANSLATION_ENGINE_METADATA_MAP[service_name]
                setattr(self.cli_settings, chosen_meta.cli_flag_name, True)

                # 3) 更新详细设置字段
                if chosen_meta.cli_detail_field_name:
                    detail_model = getattr(self.cli_settings, chosen_meta.cli_detail_field_name)
                    idxs = detail_text_input_index_map.get(service_name, [])
                    names = service_arg_names_map.get(service_name, [])
                    for local_idx, field_name in zip(idxs, names):
                        if local_idx >= len(all_args):
                            continue
                        val = all_args[local_idx]
                        type_hint = detail_model.model_fields[field_name].annotation
                        # 类型转换
                        if type_hint is str:
                            pass
                        elif type_hint is int:
                            try:
                                val = int(val)
                            except Exception:
                                val = getattr(detail_model, field_name) or 0
                        elif type_hint is bool:
                            val = bool(val)
                        else:
                            # 其他类型直接写入字符串
                            val = str(val) if val is not None else ""
                        setattr(detail_model, field_name, val)

                # 4) 校验并写入配置文件
                self.cli_settings.validate_settings()
                self.config_manager.write_user_default_config_file(settings=self.cli_settings)
                # 同步 SettingsModel（用于后续翻译调用）
                self.settings = self.cli_settings.to_settings_model()

                return gr.update(value="✅ 设置已保存，并将用于后续翻译", visible=True)
            except Exception as e:
                logger.error(f"保存设置失败: {e}", exc_info=True)
                return gr.update(value=f"❌ 保存失败: {e}", visible=True)

        save_btn.click(
            fn=apply_engine_settings,
            inputs=[service_dd] + detail_text_inputs,
            outputs=[save_status],
        )

        gr.Markdown("### 🔧 MinerU 设置（只读概览）")
        gr.Markdown(
            f"""
            **当前配置**:
            - 后端: {getattr(self.settings.mineru, 'backend', 'transformers')}
            - 模型: {getattr(self.settings.mineru, 'model_path', 'opendatalab/MinerU2.5-Pro-2604-1.2B')}
            - DPI: {getattr(self.settings.mineru, 'dpi', 260)}
            """
        )
    
    async def _handle_translation(
        self,
        pdf_file,
        title,
        translation_path,
        output_formats,
        lang_in,
        lang_out,
        progress=gr.Progress()
    ):
        """处理翻译请求
        
        集成 BabelDOC 事件流与 MinerU 管道，实时更新进度并保存结果。
        """
        if not pdf_file:
            return "请上传PDF文件", None, None, None

        try:
            # 创建项目
            project_id = self.storage.create_project(
                source_pdf=pdf_file,
                metadata={
                    'title': title or Path(pdf_file).stem,
                    'lang_in': lang_in,
                    'lang_out': lang_out,
                    'translation_path': translation_path,
                    'output_formats': output_formats if translation_path == "mineru" else []
                }
            )

            # 进度：开始处理
            progress(0.02, desc="初始化项目与配置...")

            if translation_path == "babeldoc":
                # 构建基于 CLI 的设置，并转为 SettingsModel
                cli_settings = self.cli_settings.clone()
                cli_settings.translation.lang_in = lang_in
                cli_settings.translation.lang_out = lang_out
                # 指定 BabelDOC 输出目录到项目目录
                babeldoc_dir = self.storage.projects_dir / project_id / "babeldoc"
                cli_settings.translation.output = str(babeldoc_dir)
                # 验证并转换
                cli_settings.validate_settings()
                settings: SettingsModel = cli_settings.to_settings_model()
                # 清空 input_files，使用传入的路径
                settings.basic.input_files = set()

                mono_path = None
                dual_path = None
                glossary_path = None

                # 运行 BabelDOC 翻译并映射进度
                async for event in do_translate_async_stream(settings, Path(pdf_file)):
                    etype = event.get("type")
                    if etype in ("progress_start", "progress_update", "progress_end"):
                        desc = event.get("stage", "")
                        overall = float(event.get("overall_progress", 0)) / 100.0
                        part_index = event.get("part_index", 0)
                        total_parts = event.get("total_parts", 0)
                        stage_current = event.get("stage_current", 0)
                        stage_total = event.get("stage_total", 0)
                        desc_text = f"{desc} ({part_index}/{total_parts}, {stage_current}/{stage_total})"
                        progress(max(0.0, min(1.0, overall)), desc=desc_text)
                    elif etype == "finish":
                        result = event["translate_result"]
                        mono_path = result.mono_pdf_path
                        dual_path = result.dual_pdf_path
                        glossary_path = getattr(result, "auto_extracted_glossary_path", None)
                        progress(1.0, desc="翻译完成！")
                        break
                    elif etype == "error":
                        error_msg = event.get("error", "Unknown error")
                        error_details = event.get("details", "")
                        raise gr.Error(f"翻译错误: {error_msg}")

                # 汇总并更新项目结果元数据
                result_files = []
                babeldoc_results = []
                if mono_path:
                    result_files.append(str(mono_path))
                    babeldoc_results.append(Path(mono_path).name)
                if dual_path:
                    result_files.append(str(dual_path))
                    babeldoc_results.append(Path(dual_path).name)
                if glossary_path:
                    result_files.append(str(glossary_path))
                    babeldoc_results.append(Path(glossary_path).name)

                # 更新项目状态与结果列表
                self.storage.update_project_status(
                    project_id,
                    'completed',
                    results={
                        'babeldoc': babeldoc_results
                    }
                )

                status = (
                    f"✅ 翻译完成!\n项目ID: {project_id}\n翻译路径: {translation_path}"
                )
                details = {
                    "project_id": project_id,
                    "mono_pdf_path": str(mono_path) if mono_path else None,
                    "dual_pdf_path": str(dual_path) if dual_path else None,
                    "auto_extracted_glossary_path": str(glossary_path) if glossary_path else None,
                }
                return status, details, result_files or None, project_id

            else:
                # 使用 MinerU 翻译管道
                from pdf2zh_next.mineru_pipeline import MinerUTranslationPipeline

                # 设置语言（克隆 SettingsModel，避免污染全局）
                settings_for_mineru = self.settings.clone()
                settings_for_mineru.translation.lang_in = lang_in
                settings_for_mineru.translation.lang_out = lang_out

                pipeline = MinerUTranslationPipeline(settings_for_mineru, self.storage)

                # 事件循环并更新进度
                async for event in pipeline.translate_pdf(pdf_file, project_id):
                    stage = event.get('stage', '')
                    prog = float(event.get('progress', 0.0))
                    msg = event.get('message', '')
                    progress(max(0.0, min(1.0, prog)), desc=f"{stage}: {msg}")
                    if stage == 'complete':
                        break
                    if stage == 'error':
                        raise gr.Error(f"翻译错误: {msg}")

                # 读取结果文件列表
                meta = self.storage.get_project(project_id)
                mineru_files = [
                    *meta.get('results', {}).get('mineru', [])
                ]
                result_paths = [
                    str(self.storage.get_file_path(project_id, f"mineru/{name}"))
                    for name in mineru_files
                ]

                status = (
                    f"✅ 翻译完成!\n项目ID: {project_id}\n翻译路径: {translation_path}"
                )
                details = {
                    "project_id": project_id,
                    "results": {
                        "mineru": mineru_files
                    },
                }
                return status, details, result_paths or None, project_id

        except gr.Error:
            # 直接透传 Gradio 错误（用于弹窗提醒）
            raise
        except Exception as e:
            logger.error(f"翻译失败: {e}", exc_info=True)
            return f"❌ 翻译失败: {e}", None, None, None


def launch_ui(settings: Optional[CLIEnvSettingsModel] = None, **kwargs):
    """启动UI

    Args:
        settings: 应用配置（CLIEnvSettingsModel）
        **kwargs: 传递给gr.Blocks.launch()的参数
    """
    ui = PDFTranslateUI(settings)
    app = ui.create_ui()
    
    # 默认启动参数
    launch_kwargs = {
        "server_name": "0.0.0.0",
        "server_port": 7860,
        "share": False,
        "inbrowser": True,
    }
    launch_kwargs.update(kwargs)
    
    logger.info(f"启动UI: {launch_kwargs}")
    app.launch(**launch_kwargs)


if __name__ == "__main__":
    # 允许通过环境变量控制主机与端口，便于并行预览
    import os
    host = os.getenv("PDF2ZH_UI_HOST", "0.0.0.0")
    port_str = os.getenv("PDF2ZH_UI_PORT", os.getenv("PORT", "7860"))
    try:
        port = int(port_str)
    except Exception:
        port = 7860
    launch_ui(server_name=host, server_port=port)

