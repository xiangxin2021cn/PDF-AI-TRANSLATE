"""简洁的UI主题配置 - 适度美化，专注功能"""
from __future__ import annotations

import gradio as gr


def create_clean_theme():
    """创建简洁优雅的主题

    设计原则:
    - 温暖但不过分鲜艳的配色
    - 清晰的层次结构
    - 良好的可读性
    - 适度的视觉装饰
    """

    theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.blue,
        secondary_hue=gr.themes.colors.gray,
        neutral_hue=gr.themes.colors.gray,
        font=[
            gr.themes.GoogleFont("Inter"),
            "ui-sans-serif",
            "system-ui",
            "sans-serif",
        ],
        font_mono=[
            gr.themes.GoogleFont("JetBrains Mono"),
            "ui-monospace",
            "Consolas",
            "monospace",
        ],
    ).set(
        # 背景颜色
        body_background_fill="#FAFAFA",
        body_background_fill_dark="#1A1A1A",

        # 主要按钮
        button_primary_background_fill="#3B82F6",
        button_primary_background_fill_hover="#2563EB",
        button_primary_background_fill_dark="#3B82F6",
        button_primary_text_color="white",
        button_primary_text_color_dark="white",

        # 次要按钮
        button_secondary_background_fill="white",
        button_secondary_background_fill_hover="#F3F4F6",
        button_secondary_border_color="#D1D5DB",
        button_secondary_text_color="#374151",

        # 卡片背景
        block_background_fill="white",
        block_background_fill_dark="#1F2937",
        block_border_color="#E5E7EB",
        block_border_color_dark="#374151",

        # 输入框
        input_background_fill="white",
        input_background_fill_dark="#374151",
        input_border_color="#D1D5DB",
        input_border_color_dark="#4B5563",
        input_border_width="1px",

        # 文本颜色
        body_text_color="#1F2937",
        body_text_color_dark="#F9FAFB",

        # 标题颜色
        block_title_text_color="#111827",
        block_title_text_color_dark="#F9FAFB",

        # 标签文本
        block_label_text_color="#374151",
        block_label_text_color_dark="#D1D5DB",

        # 进度条
        slider_color="#3B82F6",
        slider_color_dark="#60A5FA",

        # 错误和警告
        error_background_fill="#FEE2E2",
        error_background_fill_dark="#7F1D1D",
        error_text_color="#991B1B",
        error_text_color_dark="#FCA5A5",

        # 链接
        link_text_color="#3B82F6",
        link_text_color_dark="#60A5FA",
        link_text_color_hover="#2563EB",
        link_text_color_hover_dark="#93C5FD",
    )

    return theme


def get_clean_css():
    """获取简洁的CSS样式"""

    return """
    /* 全局样式 */
    .gradio-container {
        font-family: 'Inter', ui-sans-serif, system-ui, sans-serif;
        max-width: 1200px;
        margin: 0 auto;
        padding: 20px;
    }

    /* 标题样式 */
    h1 {
        color: #1F2937 !important;
        text-align: center;
        margin-bottom: 8px !important;
        font-weight: 700 !important;
        font-size: 2.5rem !important;
    }

    h2 {
        color: #374151 !important;
        margin-bottom: 16px !important;
        font-weight: 600 !important;
        font-size: 1.5rem !important;
        border-bottom: 2px solid #E5E7EB !important;
        padding-bottom: 8px !important;
    }

    h3 {
        color: #4B5563 !important;
        margin-bottom: 12px !important;
        font-weight: 600 !important;
        font-size: 1.2rem !important;
    }

    /* 按钮样式 */
    .gradio-button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }

    .gradio-button.primary {
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important;
        box-shadow: 0 2px 4px rgba(59, 130, 246, 0.2) !important;
    }

    .gradio-button.primary:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 8px rgba(59, 130, 246, 0.3) !important;
    }

    /* 输入框样式 */
    .gradio-textbox, .gradio-dropdown {
        border-radius: 8px !important;
        border: 1px solid #D1D5DB !important;
        transition: border-color 0.2s ease !important;
    }

    .gradio-textbox:focus, .gradio-dropdown:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1) !important;
    }

    /* 文件上传区域 */
    .gradio-file {
        border: 2px dashed #D1D5DB !important;
        border-radius: 12px !important;
        background: #FAFAFA !important;
        transition: all 0.2s ease !important;
    }

    .gradio-file:hover {
        border-color: #3B82F6 !important;
        background: #F3F4F6 !important;
    }

    /* Tab样式 */
    .gradio-tabs button {
        border-radius: 8px 8px 0 0 !important;
        font-weight: 500 !important;
        margin-right: 4px !important;
    }

    .gradio-tabs button.selected {
        background: white !important;
        border-bottom: 2px solid #3B82F6 !important;
        color: #3B82F6 !important;
    }

    /* 卡片/组样式 */
    .gradio-group {
        border-radius: 12px !important;
        border: 1px solid #E5E7EB !important;
        background: white !important;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1) !important;
    }

    /* 手风琴样式 */
    .gradio-accordion {
        border-radius: 8px !important;
        border: 1px solid #E5E7EB !important;
    }

    .gradio-accordion label {
        font-weight: 600 !important;
        color: #374151 !important;
    }

    /* 进度条样式 */
    .gradio-progress {
        border-radius: 4px !important;
        overflow: hidden !important;
    }

    .gradio-progress .progress-bar {
        background: linear-gradient(90deg, #3B82F6 0%, #60A5FA 100%) !important;
    }

    /* 数据表格样式 */
    .gradio-dataframe table {
        border-radius: 8px !important;
        overflow: hidden !important;
    }

    .gradio-dataframe th {
        background: #F9FAFB !important;
        color: #374151 !important;
        font-weight: 600 !important;
        border-bottom: 2px solid #E5E7EB !important;
    }

    .gradio-dataframe td {
        border-bottom: 1px solid #F3F4F6 !important;
    }

    .gradio-dataframe tr:hover {
        background: #F9FAFB !important;
    }

    /* HTML预览样式 */
    .gradio-html {
        border-radius: 8px !important;
        border: 1px solid #E5E7EB !important;
        background: white !important;
        padding: 16px !important;
        max-height: 600px !important;
        overflow-y: auto !important;
    }

    /* 图库样式 */
    .gradio-gallery {
        border-radius: 8px !important;
        border: 1px solid #E5E7EB !important;
        overflow: hidden !important;
    }

    /* 页脚样式 */
    footer {
        text-align: center !important;
        color: #6B7280 !important;
        font-size: 0.875rem !important;
        margin-top: 40px !important;
        padding-top: 20px !important;
        border-top: 1px solid #E5E7EB !important;
    }

    /* 深色模式适配 */
    @media (prefers-color-scheme: dark) {
        .gradio-group {
            background: #1F2937 !important;
            border-color: #374151 !important;
        }

        .gradio-file {
            background: #374151 !important;
            border-color: #4B5563 !important;
        }

        .gradio-textbox, .gradio-dropdown {
            background: #374151 !important;
            border-color: #4B5563 !important;
            color: #F9FAFB !important;
        }
    }

    /* 响应式设计 */
    @media (max-width: 768px) {
        .gradio-container {
            padding: 16px !important;
        }

        h1 {
            font-size: 2rem !important;
        }

        h2 {
            font-size: 1.25rem !important;
        }

        .gradio-button {
            font-size: 0.875rem !important;
        }
    }

    /* 加载动画 */
    .gradio-loading {
        border-radius: 8px !important;
    }

    /* 工具提示样式 */
    .gradio-tooltip {
        border-radius: 6px !important;
        background: #1F2937 !important;
        color: white !important;
        font-size: 0.875rem !important;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1) !important;
    }

    /* 错误消息样式 */
    .gradio-error {
        background: #FEE2E2 !important;
        color: #991B1B !important;
        border: 1px solid #FCA5A5 !important;
        border-radius: 8px !important;
        padding: 12px !important;
    }

    /* 成功消息样式 */
    .gradio-info {
        background: #DBEAFE !important;
        color: #1E40AF !important;
        border: 1px solid #93C5FD !important;
        border-radius: 8px !important;
        padding: 12px !important;
    }
    """