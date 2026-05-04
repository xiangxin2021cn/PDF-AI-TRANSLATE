"""UI theme configuration for the local PDF translation tool."""

from __future__ import annotations

import gradio as gr


def create_custom_theme():
    """Create a quiet, utility-focused Gradio theme."""

    theme = gr.themes.Soft(
        primary_hue=gr.themes.colors.blue,
        secondary_hue=gr.themes.colors.slate,
        neutral_hue=gr.themes.colors.slate,
        font=[
            gr.themes.GoogleFont("Inter"),
            "sans-serif",
        ],
        font_mono=[
            gr.themes.GoogleFont("IBM Plex Mono"),
            "monospace",
        ],
    ).set(
        body_background_fill="#F6F8FB",
        body_background_fill_dark="#111827",
        button_primary_background_fill="#2563EB",
        button_primary_background_fill_hover="#1D4ED8",
        button_primary_background_fill_dark="#3B82F6",
        button_primary_text_color="white",
        button_primary_text_color_dark="white",
        button_secondary_background_fill="#FFFFFF",
        button_secondary_background_fill_hover="#EEF2FF",
        button_secondary_border_color="#CBD5E1",
        button_secondary_text_color="#0F172A",
        block_background_fill="#FFFFFF",
        block_background_fill_dark="#1F2937",
        block_border_width="1px",
        block_border_color="#D8DEE9",
        block_border_color_dark="#374151",
        block_shadow="0 1px 2px rgba(15,23,42,0.05)",
        block_shadow_dark="0 1px 2px rgba(0,0,0,0.2)",
        block_title_text_weight="600",
        block_title_text_size="*text_md",
        block_title_text_color="#0F172A",
        block_title_text_color_dark="#F9FAFB",
        block_label_text_weight="500",
        block_label_text_size="*text_sm",
        block_label_text_color="#475569",
        block_label_text_color_dark="#9CA3AF",
        input_background_fill="#FFFFFF",
        input_background_fill_dark="#1F2937",
        input_background_fill_focus="#FFFFFF",
        input_background_fill_focus_dark="#1F2937",
        input_border_color="#CBD5E1",
        input_border_color_dark="#374151",
        input_border_color_focus="#2563EB",
        input_border_color_focus_dark="#60A5FA",
        input_border_width="1px",
        input_shadow="none",
        input_shadow_focus="0 0 0 3px rgba(37,99,235,0.12)",
        body_text_color="#0F172A",
        body_text_color_dark="#F9FAFB",
        body_text_color_subdued="#64748B",
        body_text_color_subdued_dark="#9CA3AF",
        checkbox_background_color="#FFFFFF",
        checkbox_background_color_selected="#2563EB",
        checkbox_background_color_dark="#1F2937",
        checkbox_background_color_selected_dark="#60A5FA",
        checkbox_border_color="#CBD5E1",
        checkbox_border_color_dark="#374151",
        checkbox_border_color_selected="#2563EB",
        checkbox_border_color_selected_dark="#60A5FA",
        slider_color="#2563EB",
        slider_color_dark="#60A5FA",
        table_border_color="#D8DEE9",
        table_border_color_dark="#374151",
        table_row_focus="#EEF2FF",
        table_row_focus_dark="#374151",
        panel_background_fill="#FFFFFF",
        panel_background_fill_dark="#1F2937",
        panel_border_color="#D8DEE9",
        panel_border_color_dark="#374151",
        panel_border_width="1px",
        color_accent="#2563EB",
        color_accent_soft="#DBEAFE",
    )

    return theme


def get_vanta_js():
    """Return optional page head content."""
    return """
    <meta name="color-scheme" content="light dark">
    <script>
    (() => {
        if (window.__pdf2zhPdfViewerToolsInstalled) {
            return;
        }
        window.__pdf2zhPdfViewerToolsInstalled = true;

        const previewIds = ["babeldoc_pdf_preview", "mineru_pdf_preview"];
        const zoomState = new Map();
        let pendingApply = null;

        const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

        const getRoot = (targetId) => {
            if (!targetId) {
                return null;
            }
            const direct = document.getElementById(targetId);
            if (direct) {
                return direct;
            }
            const escaped = window.CSS && CSS.escape ? CSS.escape(targetId) : targetId.replace(/"/g, '\\"');
            return document.querySelector(`#${escaped}`) || document.querySelector(`[id="${targetId}"]`);
        };

        const getPdfCanvasWrap = (root) => {
            if (!root) {
                return null;
            }
            return root.querySelector(".pdf-canvas") || root.querySelector('[class*="pdf-canvas"]') || root;
        };

        const getPageNodes = (root) => {
            const wrap = getPdfCanvasWrap(root);
            if (!wrap) {
                return [];
            }
            return Array.from(wrap.querySelectorAll("canvas, img")).filter((node) => {
                const rect = node.getBoundingClientRect();
                return rect.width > 80 || rect.height > 80 || node.tagName.toLowerCase() === "canvas";
            });
        };

        const updateIndicator = (targetId, scale) => {
            const indicator = document.querySelector(`[data-pdf2zh-zoom-indicator="${targetId}"]`);
            if (indicator) {
                indicator.textContent = `${Math.round(scale * 100)}%`;
            }
        };

        const applyZoom = (targetId) => {
            const root = getRoot(targetId);
            const wrap = getPdfCanvasWrap(root);
            const pages = getPageNodes(root);
            if (!root || !wrap || pages.length === 0) {
                updateIndicator(targetId, zoomState.get(targetId) || 1);
                return;
            }

            const scale = zoomState.get(targetId) || 1;
            const availableWidth = Math.max(360, Math.floor((wrap.clientWidth || root.clientWidth || 900) - 34));

            wrap.style.overflow = "auto";
            wrap.style.alignItems = "flex-start";
            pages.forEach((page) => {
                const tagName = page.tagName.toLowerCase();
                const intrinsicWidth = tagName === "canvas" ? page.width : page.naturalWidth;
                const baseWidth = intrinsicWidth && intrinsicWidth > 0
                    ? Math.min(availableWidth, intrinsicWidth)
                    : availableWidth;
                const pageWidth = Math.round(baseWidth * scale);
                page.style.width = `${pageWidth}px`;
                page.style.maxWidth = "none";
                page.style.height = "auto";
                page.style.transformOrigin = "top center";
            });
            updateIndicator(targetId, scale);
        };

        const scheduleApplyAll = () => {
            window.clearTimeout(pendingApply);
            pendingApply = window.setTimeout(() => {
                previewIds.forEach(applyZoom);
            }, 120);
        };

        window.pdf2zhPdfViewerAction = (targetId, action) => {
            const currentScale = zoomState.get(targetId) || 1;
            let nextScale = currentScale;
            if (action === "in") {
                nextScale = clamp(currentScale + 0.15, 0.55, 2.5);
            } else if (action === "out") {
                nextScale = clamp(currentScale - 0.15, 0.55, 2.5);
            } else if (action === "fit" || action === "reset") {
                nextScale = 1;
            }
            zoomState.set(targetId, nextScale);
            window.requestAnimationFrame(() => applyZoom(targetId));
            return false;
        };

        window.addEventListener("resize", scheduleApplyAll);
        document.addEventListener("DOMContentLoaded", scheduleApplyAll);
        new MutationObserver(scheduleApplyAll).observe(document.documentElement, {
            childList: true,
            subtree: true,
        });
    })();
    </script>
    """


def get_custom_css():
    """Return compact CSS for the operational desktop-style UI."""
    return """
    .gradio-container {
        background: #F6F8FB !important;
        max-width: 1680px !important;
        padding: 14px 18px 22px !important;
    }

    :root {
        --tool-bg: #F6F8FB;
        --tool-surface: #FFFFFF;
        --tool-surface-muted: #F1F5F9;
        --tool-border: #D8DEE9;
        --tool-text: #0F172A;
        --tool-muted: #64748B;
        --tool-accent: #2563EB;
        --tool-accent-soft: #DBEAFE;
        --tool-danger: #B42318;
    }

    h1 {
        color: var(--tool-text) !important;
        font-size: 1.65rem !important;
        font-weight: 700 !important;
        margin: 0.35rem 0 0.1rem !important;
        letter-spacing: 0 !important;
        text-align: left !important;
    }

    h2 {
        color: var(--tool-text) !important;
        font-size: 1.05rem !important;
        font-weight: 600 !important;
        margin: 0.65rem 0 0.45rem !important;
        letter-spacing: 0 !important;
        text-align: left !important;
    }

    h3 {
        color: var(--tool-text) !important;
        font-size: 0.98rem !important;
        font-weight: 600 !important;
        margin: 0.55rem 0 0.35rem !important;
        letter-spacing: 0 !important;
        text-align: left !important;
    }

    p, label, .markdown-text {
        color: var(--tool-muted) !important;
    }

    .prose {
        max-width: none !important;
    }

    .contain, .form, .panel, .block {
        border-radius: 8px !important;
    }

    .app-hero {
        position: relative;
        display: grid;
        grid-template-columns: minmax(0, 1fr) minmax(330px, 440px);
        align-items: center;
        gap: 28px;
        min-height: 205px;
        margin: 0 0 14px;
        padding: 26px 30px;
        overflow: hidden;
        border: 1px solid rgba(147, 197, 253, 0.46);
        border-radius: 8px;
        background:
            linear-gradient(112deg, rgba(241, 248, 255, 0.98) 0%, rgba(232, 244, 255, 0.96) 38%, rgba(255, 255, 255, 0.98) 76%, rgba(239, 247, 255, 0.96) 100%);
        box-shadow: 0 18px 42px rgba(37, 99, 235, 0.11), inset 0 1px 0 rgba(255, 255, 255, 0.82);
    }

    .app-hero::before {
        content: "";
        position: absolute;
        inset: 0;
        background:
            linear-gradient(90deg, rgba(37, 99, 235, 0.08), transparent 34%),
            linear-gradient(180deg, rgba(255, 255, 255, 0.68), transparent 54%);
        pointer-events: none;
    }

    .app-hero::after {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(110deg, transparent 0%, rgba(255,255,255,0.62) 42%, transparent 72%);
        transform: translateX(-120%);
        animation: hero-sheen 8s ease-in-out infinite;
        pointer-events: none;
    }

    @keyframes hero-sheen {
        0%, 48% { transform: translateX(-120%); }
        72%, 100% { transform: translateX(120%); }
    }

    .app-hero-copy {
        position: relative;
        z-index: 1;
    }

    .app-hero-kicker {
        margin-bottom: 6px;
        color: #1D4ED8;
        font-family: "Aptos Display", "Segoe UI Variable Display", "Segoe UI", Arial, sans-serif !important;
        font-size: 0.76rem;
        font-weight: 800;
        letter-spacing: 0;
        text-transform: none;
    }

    .app-hero-kicker .brand-pi {
        font-family: "Cambria Math", "STIX Two Math", "Times New Roman", serif !important;
        font-size: 1.16em;
        font-weight: 700;
        line-height: 1;
        vertical-align: -0.03em;
    }

    .app-hero h1 {
        margin: 0 0 8px !important;
        color: #0B1220 !important;
        font-size: 2.22rem !important;
        line-height: 1.1 !important;
    }

    .app-hero p {
        max-width: 760px;
        margin: 0 !important;
        color: #334155 !important;
        font-size: 0.98rem !important;
        line-height: 1.6 !important;
    }

    .app-hero-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
        margin-top: 14px;
    }

    .app-hero-pills span {
        display: inline-flex;
        align-items: center;
        min-height: 26px;
        padding: 3px 10px;
        border: 1px solid rgba(37, 99, 235, 0.2);
        border-radius: 999px;
        background: rgba(255,255,255,0.72);
        color: #1E40AF;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .app-hero-art {
        position: relative;
        z-index: 1;
        display: flex;
        justify-content: flex-end;
        align-items: center;
        min-width: 0;
        padding-right: 0;
    }

    .app-hero-logo {
        width: min(100%, 380px);
        max-height: 190px;
        height: auto;
        object-fit: contain;
        border: 0;
        border-radius: 0;
        filter: drop-shadow(0 22px 26px rgba(15, 23, 42, 0.27)) drop-shadow(0 3px 0 rgba(255, 255, 255, 0.82));
        transform: translateZ(0);
    }

    .app-subtitle p {
        margin: 0 0 0.75rem !important;
        color: #475569 !important;
        font-size: 0.95rem !important;
    }

    .secondary-text, .secondary-text * {
        color: #64748B !important;
        font-size: 0.82rem !important;
        line-height: 1.45 !important;
    }

    .tab-nav button {
        color: var(--tool-muted) !important;
        font-weight: 600 !important;
        border-bottom: 2px solid transparent !important;
        border-radius: 0 !important;
    }

    .tab-nav button:hover,
    .tab-nav button.selected {
        color: var(--tool-accent) !important;
        border-bottom-color: var(--tool-accent) !important;
    }

    button {
        border-radius: 7px !important;
        box-shadow: none !important;
    }

    input, textarea, select {
        border-radius: 7px !important;
    }

    .table-wrap, .grid-wrap, table {
        font-size: 0.86rem !important;
    }

    .history-card-list {
        display: grid;
        grid-template-columns: 1fr;
        gap: 8px;
        margin: 2px 0 10px;
    }

    .history-card {
        display: grid;
        grid-template-columns: 38px minmax(0, 1fr) auto;
        align-items: center;
        gap: 10px;
        padding: 10px 12px;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        background: #FFFFFF;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }

    .history-card-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 8px;
        background: #EFF6FF;
        color: #1D4ED8;
        font-size: 0.86rem;
        font-weight: 800;
    }

    .history-card-main {
        min-width: 0;
    }

    .history-card-name {
        overflow: hidden;
        color: #0F172A;
        font-size: 0.9rem;
        font-weight: 700;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .history-card-meta,
    .history-card-source {
        overflow: hidden;
        color: #64748B;
        font-size: 0.76rem;
        line-height: 1.35;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    .history-card-status {
        padding: 3px 8px;
        border-radius: 999px;
        background: #ECFDF5;
        color: #047857;
        font-size: 0.74rem;
        font-weight: 700;
    }

    .history-card-picker {
        margin: 2px 0 10px !important;
    }

    .history-card-picker .wrap {
        display: grid !important;
        gap: 8px !important;
    }

    .history-card-picker label {
        display: flex !important;
        align-items: center !important;
        gap: 10px !important;
        min-height: 46px !important;
        padding: 10px 12px !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 8px !important;
        background: #FFFFFF !important;
        color: #0F172A !important;
        font-weight: 650 !important;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04) !important;
        cursor: pointer !important;
    }

    .history-card-picker label:hover {
        border-color: rgba(37, 99, 235, 0.36) !important;
        background: #F8FBFF !important;
    }

    .history-card-picker input[type="radio"] {
        accent-color: #2563EB !important;
    }

    .history-empty {
        padding: 18px;
        border: 1px dashed #CBD5E1;
        border-radius: 8px;
        background: #F8FAFC;
        text-align: center;
    }

    .history-empty-title {
        color: #0F172A;
        font-weight: 700;
    }

    .history-empty-subtitle {
        margin-top: 4px;
        color: #64748B;
        font-size: 0.84rem;
    }

    .history-picker label {
        font-weight: 700 !important;
    }

    .pdf-preview-toolbar {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
        margin: 4px 0 8px;
        padding: 8px 10px;
        border: 1px solid #D8E4F3;
        border-radius: 8px;
        background: linear-gradient(180deg, #FFFFFF 0%, #F7FAFF 100%);
    }

    .pdf-preview-toolbar-title {
        color: #0F172A;
        font-size: 0.88rem;
        font-weight: 750;
    }

    .pdf-preview-actions {
        display: flex;
        align-items: center;
        gap: 6px;
        min-width: 0;
    }

    .pdf-preview-actions button {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-width: 34px;
        height: 32px;
        padding: 0 10px;
        border: 1px solid #CBD5E1;
        border-radius: 7px;
        background: #FFFFFF;
        color: #0F172A;
        font-size: 0.86rem;
        font-weight: 750;
        line-height: 1;
        cursor: pointer;
    }

    .pdf-preview-actions button:hover {
        border-color: rgba(37, 99, 235, 0.42);
        background: #EFF6FF;
        color: #1D4ED8;
    }

    .pdf-preview-zoom-value {
        min-width: 48px;
        color: #334155;
        font-size: 0.82rem;
        font-weight: 750;
        text-align: center;
        font-variant-numeric: tabular-nums;
    }

    .pdf-canvas,
    .pdf-canvas canvas {
        background: var(--tool-surface-muted) !important;
    }

    .pdf-viewer-zoomable .pdf-canvas,
    .pdf-viewer-zoomable [class*="pdf-canvas"] {
        align-items: flex-start !important;
        justify-content: center !important;
        height: min(74vh, 860px) !important;
        min-height: 680px !important;
        padding: 16px !important;
        overflow: auto !important;
        border-radius: 8px !important;
        background: #EEF4FA !important;
    }

    #babeldoc_pdf_preview .pdf-canvas,
    #babeldoc_pdf_preview [class*="pdf-canvas"] {
        height: min(78vh, 920px) !important;
        min-height: 780px !important;
    }

    #mineru_pdf_preview .pdf-canvas,
    #mineru_pdf_preview [class*="pdf-canvas"] {
        height: min(72vh, 780px) !important;
        min-height: 660px !important;
    }

    .pdf-viewer-zoomable .pdf-canvas canvas,
    .pdf-viewer-zoomable [class*="pdf-canvas"] canvas,
    .pdf-viewer-zoomable .pdf-canvas img,
    .pdf-viewer-zoomable [class*="pdf-canvas"] img {
        display: block !important;
        max-width: none !important;
        height: auto !important;
        border-radius: 4px !important;
        background: #FFFFFF !important;
        box-shadow: 0 14px 34px rgba(15, 23, 42, 0.18) !important;
    }

    @media (max-width: 768px) {
        .gradio-container {
            padding: 10px !important;
        }

        h1 {
            font-size: 1.35rem !important;
        }

        .app-hero {
            grid-template-columns: 1fr;
            padding: 18px;
            gap: 16px;
        }

        .app-hero h1 {
            font-size: 1.55rem !important;
        }

        .app-hero-art {
            justify-content: flex-start;
        }

        .app-hero-logo {
            width: min(72vw, 220px);
            max-height: 120px;
        }

        h2, h3 {
            font-size: 0.98rem !important;
        }

        .pdf-preview-toolbar {
            align-items: flex-start;
            flex-direction: column;
        }

        .pdf-viewer-zoomable .pdf-canvas,
        .pdf-viewer-zoomable [class*="pdf-canvas"] {
            height: min(68vh, 620px) !important;
            min-height: 520px !important;
            padding: 10px !important;
        }
    }
    """
