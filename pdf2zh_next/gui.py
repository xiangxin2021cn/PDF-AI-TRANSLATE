import asyncio
import cgi
import csv
import html as html_lib
import io
import json
import logging
import os
import re
import shutil
import tempfile
import time
import typing
import uuid
from datetime import datetime
from pathlib import Path
from string import Template
from urllib.parse import quote

import chardet
import gradio as gr
import requests
from babeldoc import __version__ as babeldoc_version
from gradio_pdf import PDF

from pdf2zh_next import __version__
from pdf2zh_next.config import ConfigManager
from pdf2zh_next.config.cli_env_model import CLIEnvSettingsModel
from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.config.translate_engine_model import GUI_PASSWORD_FIELDS
from pdf2zh_next.config.translate_engine_model import GUI_SENSITIVE_FIELDS
from pdf2zh_next.config.translate_engine_model import TRANSLATION_ENGINE_METADATA
from pdf2zh_next.config.translate_engine_model import TRANSLATION_ENGINE_METADATA_MAP
from pdf2zh_next.high_level import TranslationError
from pdf2zh_next.high_level import do_translate_async_stream
from pdf2zh_next.markdown_translator import translate_markdown_file
from pdf2zh_next.markdown_smart_translator import translate_markdown_smart
from pdf2zh_next.markdown_preview import MarkdownPreview
from pdf2zh_next.markdown_assets import embed_markdown_images_as_data_uris
from pdf2zh_next.mineru_optimized_pipeline import MinerUOptimizedPipeline
from pdf2zh_next.storage_manager import StorageManager
from pdf2zh_next.document_viewer import DocumentViewer
from pdf2zh_next.gui_theme import create_custom_theme, get_custom_css, get_vanta_js

logger = logging.getLogger(__name__)
__gui_service_arg_names = []
# The following variables associate strings with specific languages
lang_map = {
    "English": "en",
    "Simplified Chinese": "zh-CN",
    "Traditional Chinese - Hong Kong": "zh-HK",
    "Traditional Chinese - Taiwan": "zh-TW",
    "Japanese": "ja",
    "Korean": "ko",
    "Polish": "pl",
    "Russian": "ru",
    "Spanish": "es",
    "Portuguese": "pt",
    "Brazilian Portuguese": "pt-BR",
    "French": "fr",
    "Malay": "ms",
    "Indonesian": "id",
    "Turkmen": "tk",
    "Filipino (Tagalog)": "tl",
    "Vietnamese": "vi",
    "Kazakh (Latin)": "kk",
    "German": "de",
    "Dutch": "nl",
    "Irish": "ga",
    "Italian": "it",
    "Greek": "el",
    "Swedish": "sv",
    "Danish": "da",
    "Norwegian": "no",
    "Icelandic": "is",
    "Finnish": "fi",
    "Ukrainian": "uk",
    "Czech": "cs",
    "Romanian": "ro",  # Covers Romanian, Moldovan, Moldovan (Cyrillic)
    "Hungarian": "hu",
    "Slovak": "sk",
    "Croatian": "hr",  # Also listed later, keep first
    "Estonian": "et",
    "Latvian": "lv",
    "Lithuanian": "lt",
    "Belarusian": "be",
    "Macedonian": "mk",
    "Albanian": "sq",
    "Serbian (Cyrillic)": "sr",  # Covers Serbian (Latin) too
    "Slovenian": "sl",
    "Catalan": "ca",
    "Bulgarian": "bg",
    "Maltese": "mt",
    "Swahili": "sw",
    "Amharic": "am",
    "Oromo": "om",
    "Tigrinya": "ti",
    "Haitian Creole": "ht",
    "Latin": "la",
    "Lao": "lo",
    "Malayalam": "ml",
    "Gujarati": "gu",
    "Thai": "th",
    "Burmese": "my",
    "Tamil": "ta",
    "Telugu": "te",
    "Oriya": "or",  # Also listed later, keep first
    "Armenian": "hy",
    "Mongolian (Cyrillic)": "mn",
    "Georgian": "ka",
    "Khmer": "km",
    "Bosnian": "bs",
    "Luxembourgish": "lb",
    "Romansh": "rm",
    "Turkish": "tr",
    "Sinhala": "si",
    "Uzbek": "uz",
    "Kyrgyz": "ky",  # Listed as Kirghiz later, keep this one
    "Tajik": "tg",
    "Abkhazian": "ab",
    "Afar": "aa",
    "Afrikaans": "af",
    "Akan": "ak",
    "Aragonese": "an",
    "Avaric": "av",
    "Ewe": "ee",
    "Aymara": "ay",
    "Ojibwa": "oj",
    "Occitan": "oc",
    "Ossetian": "os",
    "Pali": "pi",
    "Bashkir": "ba",
    "Basque": "eu",
    "Breton": "br",
    "Chamorro": "ch",
    "Chechen": "ce",
    "Chuvash": "cv",
    "Tswana": "tn",
    "Ndebele, South": "nr",
    "Ndonga": "ng",
    "Faroese": "fo",
    "Fijian": "fj",
    "Frisian, Western": "fy",
    "Ganda": "lg",
    "Kongo": "kg",
    "Kalaallisut": "kl",
    "Church Slavic": "cu",
    "Guarani": "gn",
    "Interlingua": "ia",
    "Herero": "hz",
    "Kikuyu": "ki",
    "Rundi": "rn",
    "Kinyarwanda": "rw",
    "Galician": "gl",
    "Kanuri": "kr",
    "Cornish": "kw",
    "Komi": "kv",
    "Xhosa": "xh",
    "Corsican": "co",
    "Cree": "cr",
    "Quechua": "qu",
    "Kurdish (Latin)": "ku",
    "Kuanyama": "kj",
    "Limburgan": "li",
    "Lingala": "ln",
    "Manx": "gv",
    "Malagasy": "mg",
    "Marshallese": "mh",
    "Maori": "mi",
    "Navajo": "nv",
    "Nauru": "na",
    "Nyanja": "ny",
    "Norwegian Nynorsk": "nn",
    "Sardinian": "sc",
    "Northern Sami": "se",
    "Samoan": "sm",
    "Sango": "sg",
    "Shona": "sn",
    "Esperanto": "eo",
    "Scottish Gaelic": "gd",
    "Somali": "so",
    "Southern Sotho": "st",
    "Tatar": "tt",
    "Tahitian": "ty",
    "Tongan": "to",
    "Twi": "tw",
    "Walloon": "wa",
    "Welsh": "cy",
    "Venda": "ve",
    "Volapük": "vo",
    "Interlingue": "ie",
    "Hiri Motu": "ho",
    "Igbo": "ig",
    "Ido": "io",
    "Inuktitut": "iu",
    "Inupiaq": "ik",
    "Sichuan Yi": "ii",
    "Yoruba": "yo",
    "Zhuang": "za",
    "Tsonga": "ts",
    "Zulu": "zu",
}

rev_lang_map = {v: k for k, v in lang_map.items()}

# The following variable associate strings with page ranges
page_map = {
    "All": None,
    "First": [0],
    "First 5 pages": list(range(0, 5)),
    "Range": None,  # User-defined range
}

UI_LANGUAGE_DEFAULT = "zh"
UI_LANGUAGE_CHOICES = [
    ("中文", "zh"),
    ("English", "en"),
    ("中英双语", "bilingual"),
]

ENGINE_FIELD_LABELS_ZH = {
    "deepl_auth_key": "DeepL 授权密钥",
    "openai_model": "OpenAI 模型",
    "openai_base_url": "OpenAI API 地址",
    "openai_api_key": "OpenAI API Key",
    "openai_temperature": "OpenAI 温度参数",
    "openai_reasoning_effort": "OpenAI 推理强度",
    "openai_timeout_seconds": "OpenAI 请求超时(秒)",
    "openai_max_tokens": "OpenAI 最大输出 tokens",
    "openai_response_format": "OpenAI 响应格式",
    "openai_thinking_type": "OpenAI 思考模式",
    "openai_send_thinking": "向 OpenAI 发送 thinking 参数",
    "openai_send_temprature": "向 OpenAI 发送 temperature 参数",
    "openai_send_reasoning_effort": "向 OpenAI 发送 reasoning_effort 参数",
    "deepseek_model": "DeepSeek 模型",
    "deepseek_base_url": "DeepSeek API 地址",
    "deepseek_api_key": "DeepSeek API Key",
    "deepseek_timeout_seconds": "DeepSeek 请求超时(秒)",
    "deepseek_thinking_type": "DeepSeek 思考模式",
    "deepseek_send_thinking": "向 DeepSeek 发送 thinking 参数",
    "deepseek_reasoning_effort": "DeepSeek 推理强度",
    "deepseek_send_reasoning_effort": "向 DeepSeek 发送 reasoning_effort 参数",
    "deepseek_max_tokens": "DeepSeek 最大输出 tokens",
    "ollama_model": "Ollama 模型",
    "ollama_host": "Ollama 服务地址",
    "num_predict": "最大预测 token 数",
    "xinference_model": "Xinference 模型",
    "xinference_host": "Xinference 服务地址",
    "azure_openai_model": "Azure OpenAI 模型",
    "azure_openai_base_url": "Azure OpenAI API 地址",
    "azure_openai_api_key": "Azure OpenAI API Key",
    "azure_openai_api_version": "Azure OpenAI API 版本",
    "modelscope_model": "ModelScope 模型",
    "modelscope_api_key": "ModelScope API Key",
    "zhipu_model": "智谱模型",
    "zhipu_base_url": "智谱 API 地址",
    "zhipu_api_key": "智谱 API Key",
    "zhipu_timeout_seconds": "智谱请求超时(秒)",
    "siliconflow_base_url": "硅基流动 API 地址",
    "siliconflow_model": "硅基流动模型",
    "siliconflow_api_key": "硅基流动 API Key",
    "siliconflow_enable_thinking": "启用思考模式",
    "siliconflow_send_enable_thinking_param": "发送 enable_thinking 参数",
    "tencentcloud_secret_id": "腾讯云 Secret ID",
    "tencentcloud_secret_key": "腾讯云 Secret Key",
    "gemini_model": "Gemini 模型",
    "gemini_api_key": "Gemini API Key",
    "azure_endpoint": "Azure 翻译服务地址",
    "azure_api_key": "Azure API Key",
    "anythingllm_url": "AnythingLLM 地址",
    "anythingllm_apikey": "AnythingLLM API Key",
    "dify_url": "Dify 地址",
    "dify_apikey": "Dify API Key",
    "grok_model": "Grok 模型",
    "grok_api_key": "Grok API Key",
    "groq_model": "Groq 模型",
    "groq_api_key": "Groq API Key",
    "qwenmt_model": "Qwen-MT 模型",
    "qwenmt_base_url": "Qwen-MT API 地址",
    "qwenmt_api_key": "Qwen-MT API Key",
    "ali_domains": "Qwen-MT 翻译领域",
    "qwenmt_timeout_seconds": "Qwen-MT 请求超时(秒)",
    "openai_compatible_model": "OpenAI 兼容模型",
    "openai_compatible_base_url": "OpenAI 兼容 API 地址",
    "openai_compatible_api_key": "OpenAI 兼容 API Key",
    "openai_compatible_temperature": "OpenAI 兼容温度参数",
    "openai_compatible_reasoning_effort": "OpenAI 兼容推理强度",
    "openai_compatible_timeout_seconds": "OpenAI 兼容请求超时(秒)",
    "openai_compatible_max_tokens": "OpenAI 兼容最大输出 tokens",
    "openai_compatible_response_format": "OpenAI 兼容响应格式",
    "openai_compatible_thinking_type": "OpenAI 兼容思考模式",
    "openai_compatible_send_temperature": "向 OpenAI 兼容服务发送 temperature 参数",
    "openai_compatible_send_reasoning_effort": "向 OpenAI 兼容服务发送 reasoning_effort 参数",
    "openai_compatible_send_thinking": "向 OpenAI 兼容服务发送 thinking 参数",
}


def ui_text(zh_text: str, en_text: str, language: str = UI_LANGUAGE_DEFAULT) -> str:
    if language == "en":
        return en_text
    if language == "bilingual":
        return f"{zh_text} / {en_text}"
    return zh_text


def ui_markdown(zh_text: str, en_text: str, language: str = UI_LANGUAGE_DEFAULT) -> str:
    return ui_text(zh_text, en_text, language)


def engine_field_label(
    field_name: str,
    english_label: str | None,
    language: str = UI_LANGUAGE_DEFAULT,
) -> str:
    english_text = english_label or field_name.replace("_", " ")
    zh_text = ENGINE_FIELD_LABELS_ZH.get(field_name)
    if not zh_text:
        normalized_name = field_name.replace("_", " ")
        if field_name.endswith(("api_key", "apikey", "auth_key")):
            zh_text = f"{normalized_name} / API Key"
        elif field_name.endswith(("base_url", "url", "endpoint", "host")):
            zh_text = f"{normalized_name} / 服务地址"
        elif field_name.endswith("model"):
            zh_text = f"{normalized_name} / 模型"
        elif field_name.endswith("timeout_seconds"):
            zh_text = f"{normalized_name} / 请求超时(秒)"
        else:
            zh_text = normalized_name
    return ui_text(zh_text, english_text, language)


def file_type_choices(language: str = UI_LANGUAGE_DEFAULT) -> list[tuple[str, str]]:
    return [
        (ui_text("文件", "File", language), "File"),
        (ui_text("链接", "Link", language), "Link"),
    ]


def page_range_choices(language: str = UI_LANGUAGE_DEFAULT) -> list[tuple[str, str]]:
    return [
        (ui_text("全部", "All", language), "All"),
        (ui_text("第一页", "First", language), "First"),
        (ui_text("前 5 页", "First 5 pages", language), "First 5 pages"),
        (ui_text("自定义范围", "Range", language), "Range"),
    ]


def rate_limit_mode_choices(
    language: str = UI_LANGUAGE_DEFAULT,
) -> list[tuple[str, str]]:
    return [
        (ui_text("每分钟请求数 RPM", "RPM (Requests Per Minute)", language), "RPM"),
        (ui_text("并发请求数", "Concurrent Requests", language), "Concurrent Threads"),
        (ui_text("自定义", "Custom", language), "Custom"),
    ]


def watermark_mode_choices(
    language: str = UI_LANGUAGE_DEFAULT,
) -> list[tuple[str, str]]:
    return [
        (ui_text("加水印", "Watermarked", language), "Watermarked"),
        (ui_text("无水印", "No Watermark", language), "No Watermark"),
    ]


def mineru_output_format_choices(
    language: str = UI_LANGUAGE_DEFAULT,
) -> list[tuple[str, str]]:
    return [
        (ui_text("Markdown", "Markdown", language), "Markdown"),
        (ui_text("HTML", "HTML", language), "HTML"),
        (ui_text("两者都导出", "Both", language), "Both"),
    ]


# Load configuration
config_manager = ConfigManager()
try:
    # Load configuration from files and environment variables
    settings = config_manager.initialize_cli_config()
    # Check if sensitive inputs should be disabled in GUI
    disable_sensitive_input = settings.gui_settings.disable_gui_sensitive_input
except Exception as e:
    logger.warning(f"Could not load initial config: {e}")
    fallback_settings = config_manager.config_cli_settings
    settings = fallback_settings.clone() if fallback_settings else CLIEnvSettingsModel()
    disable_sensitive_input = settings.gui_settings.disable_gui_sensitive_input

# Define default values
default_lang_from = rev_lang_map.get(settings.translation.lang_in, "English")

default_lang_to = settings.translation.lang_out
for display_name, code in lang_map.items():
    if code == default_lang_to:
        default_lang_to = display_name
        break
else:
    default_lang_to = "Simplified Chinese"  # Fallback

# Available translation services
# This will eventually be dynamically determined based on available translators
available_services = [x.translate_engine_type for x in TRANSLATION_ENGINE_METADATA]

if settings.gui_settings.enabled_services:
    enabled_services = {
        x.lower() for x in settings.gui_settings.enabled_services.split(",")
    }
    available_services = [
        x for x in available_services if x.lower() in enabled_services
    ]

assert available_services, "No translation service is enabled"


def _get_selected_translation_service() -> str:
    for metadata in TRANSLATION_ENGINE_METADATA:
        if getattr(settings, metadata.cli_flag_name, False):
            service_name = metadata.translate_engine_type
            if service_name in available_services:
                return service_name
    return available_services[0]


def _get_selected_translation_service_from_cli(cli_env: CLIEnvSettingsModel) -> str:
    for metadata in TRANSLATION_ENGINE_METADATA:
        if getattr(cli_env, metadata.cli_flag_name, False):
            service_name = metadata.translate_engine_type
            if service_name in available_services:
                return service_name
    return available_services[0]


def _initialize_cli_config_for_gui_editing() -> CLIEnvSettingsModel:
    current_config_manager = ConfigManager()
    try:
        return current_config_manager.initialize_cli_config()
    except Exception as e:
        logger.warning(f"Load config without final validation for GUI editing: {e}")
        cli_env = current_config_manager.config_cli_settings
        return cli_env.clone() if cli_env else CLIEnvSettingsModel()


def _is_blank_gui_value(value) -> bool:
    return value is None or value == ""


def _should_preserve_blank_engine_field(field_name: str, value) -> bool:
    return field_name in GUI_SENSITIVE_FIELDS and _is_blank_gui_value(value)


def _apply_translation_engine_gui_values(
    cli_env: CLIEnvSettingsModel,
    service_name: str,
    field_names: list[str],
    field_service_names: list[str],
    field_values: tuple,
) -> None:
    for metadata in TRANSLATION_ENGINE_METADATA:
        setattr(
            cli_env,
            metadata.cli_flag_name,
            metadata.translate_engine_type == service_name,
        )

    metadata = TRANSLATION_ENGINE_METADATA_MAP.get(service_name)
    if not metadata or not metadata.cli_detail_field_name:
        return
    if not hasattr(cli_env, metadata.cli_detail_field_name):
        return

    detail_settings = getattr(cli_env, metadata.cli_detail_field_name)
    for field_name, owner_service, value in zip(
        field_names,
        field_service_names,
        field_values,
        strict=False,
    ):
        if owner_service != service_name:
            continue
        if field_name in {"translate_engine_type", "support_llm"}:
            continue
        if _should_preserve_blank_engine_field(field_name, value):
            continue
        setattr(detail_settings, field_name, None if value == "" else value)


def _persist_translation_engine_gui_defaults(
    service_name: str,
    field_names: list[str],
    field_service_names: list[str],
    field_values: tuple,
) -> tuple[bool, str]:
    if not service_name or service_name not in TRANSLATION_ENGINE_METADATA_MAP:
        return False, "请选择翻译引擎后再保存。"

    try:
        current_config_manager = ConfigManager()
        cli_env = _initialize_cli_config_for_gui_editing()
        if cli_env.gui_settings.disable_config_auto_save:
            return False, "当前已关闭自动配置保存，请先开启配置保存后再操作。"

        _apply_translation_engine_gui_values(
            cli_env,
            service_name,
            field_names,
            field_service_names,
            field_values,
        )

        cli_env.basic.gui = False
        cli_env.basic.debug = False
        current_config_manager.write_user_default_config_file(settings=cli_env)
        return True, f"{service_name} 设置已保存，刷新页面后仍会保留。"
    except Exception:
        logger.exception("Failed to persist translation engine GUI defaults")
        return False, "保存失败，请查看终端日志。"


def _translation_engine_status_update(ok: bool, message: str):
    prefix = "✅" if ok else "❌"
    return gr.update(value=f"{prefix} {message}", visible=True)


def _parse_connection_timeout(value) -> float:
    if value in (None, ""):
        return 15.0
    try:
        timeout = float(value)
    except (TypeError, ValueError):
        return 15.0
    if timeout <= 0:
        return 15.0
    return min(timeout, 30.0)


def _chat_completions_url(base_url: str | None) -> str:
    url = (base_url or "https://api.openai.com/v1").strip().rstrip("/")
    if url.endswith("/chat/completions"):
        return url
    return f"{url}/chat/completions"


def _sanitize_connection_message(text: str | None) -> str:
    if not text:
        return ""
    clean = re.sub(r"Bearer\s+[A-Za-z0-9._\-]+", "Bearer ***", text)
    clean = re.sub(r"sk-[A-Za-z0-9._\-]+", "sk-***", clean)
    clean = re.sub(r"[A-Za-z0-9_\-]{24,}", "***", clean)
    clean = " ".join(clean.split())
    return clean[:220]


def _get_selected_engine_detail_settings(
    service_name: str,
    field_names: list[str],
    field_service_names: list[str],
    field_values: tuple,
):
    cli_env = _initialize_cli_config_for_gui_editing()
    _apply_translation_engine_gui_values(
        cli_env,
        service_name,
        field_names,
        field_service_names,
        field_values,
    )
    metadata = TRANSLATION_ENGINE_METADATA_MAP.get(service_name)
    if not metadata:
        raise ValueError("请选择有效的翻译引擎。")
    if not metadata.cli_detail_field_name:
        return None, metadata
    if not hasattr(cli_env, metadata.cli_detail_field_name):
        raise ValueError(f"{service_name} 的设置项不存在。")
    return getattr(cli_env, metadata.cli_detail_field_name), metadata


def _test_translation_engine_connection(
    service_name: str,
    field_names: list[str],
    field_service_names: list[str],
    field_values: tuple,
) -> tuple[bool, str]:
    if not service_name or service_name not in TRANSLATION_ENGINE_METADATA_MAP:
        return False, "请选择翻译引擎后再测试。"

    try:
        detail_settings, metadata = _get_selected_engine_detail_settings(
            service_name,
            field_names,
            field_service_names,
            field_values,
        )
        if detail_settings is None:
            return True, f"{service_name} 无需额外密钥，配置可用。"

        if hasattr(detail_settings, "validate_settings"):
            detail_settings.validate_settings()

        openai_like_settings = detail_settings
        if hasattr(detail_settings, "transform"):
            openai_like_settings = detail_settings.transform()

        if all(
            hasattr(openai_like_settings, attr)
            for attr in ("openai_model", "openai_api_key", "openai_base_url")
        ):
            if hasattr(openai_like_settings, "validate_settings"):
                openai_like_settings.validate_settings()
            timeout = _parse_connection_timeout(
                getattr(openai_like_settings, "openai_timeout_seconds", None)
            )
            response = requests.post(
                _chat_completions_url(openai_like_settings.openai_base_url),
                headers={
                    "Authorization": f"Bearer {openai_like_settings.openai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": openai_like_settings.openai_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 1,
                },
                timeout=timeout,
            )
            if 200 <= response.status_code < 300:
                return True, f"{service_name} 连接测试通过。"
            details = _sanitize_connection_message(response.text)
            suffix = f"，返回：{details}" if details else ""
            return (
                False,
                f"{service_name} 连接失败，HTTP {response.status_code}{suffix}",
            )

        return True, f"{service_name} 配置校验通过。"
    except requests.Timeout:
        return False, f"{service_name} 连接超时，请检查网络、Base URL 或超时设置。"
    except requests.RequestException as e:
        message = _sanitize_connection_message(str(e))
        return False, f"{service_name} 连接失败：{message}"
    except Exception as e:
        message = _sanitize_connection_message(str(e))
        return False, f"{service_name} 配置不可用：{message}"


def _load_translation_engine_gui_updates(
    field_names: list[str],
    field_service_names: list[str],
):
    try:
        cli_env = _initialize_cli_config_for_gui_editing()
        service_name = _get_selected_translation_service_from_cli(cli_env)
        updates = [
            gr.update(value=service_name),
            gr.update(visible=service_name == "SiliconFlowFree"),
        ]
        for field_name, owner_service in zip(
            field_names, field_service_names, strict=False
        ):
            value = None
            metadata = TRANSLATION_ENGINE_METADATA_MAP.get(owner_service)
            if (
                metadata
                and metadata.cli_detail_field_name
                and hasattr(cli_env, metadata.cli_detail_field_name)
            ):
                detail_settings = getattr(cli_env, metadata.cli_detail_field_name)
                value = getattr(detail_settings, field_name, None)
            updates.append(
                gr.update(value=value, visible=owner_service == service_name)
            )
        return updates
    except Exception:
        logger.exception("Failed to load translation engine GUI defaults")
        return [gr.update(), gr.update()] + [gr.update() for _ in field_names]


selected_translation_service = _get_selected_translation_service()


disable_gui_sensitive_input = settings.gui_settings.disable_gui_sensitive_input

OUTPUT_ROOT = Path("output")
OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
configured_storage_root = getattr(settings, "storage_root", "output") or "output"
history_storage_root = (
    "output" if configured_storage_root == "storage" else configured_storage_root
)

# Initialize history and MinerU components. GUI-generated documents are stored under output/.
storage_manager = StorageManager(history_storage_root)
document_viewer = DocumentViewer(max_pdf_pages=10)
HISTORY_TABLE_HEADERS = [
    "项目ID",
    "路线",
    "原文件",
    "类型",
    "文件名",
    "创建时间",
    "状态",
    "文件路径",
]
HISTORY_FILE_PATH_INDEX = len(HISTORY_TABLE_HEADERS) - 1
HISTORY_FILE_TYPE_INDEX = 3
HISTORY_FILE_NAME_INDEX = 4
HISTORY_CREATED_AT_INDEX = 5
HISTORY_VISIBLE_SUFFIXES = {".pdf", ".md", ".markdown"}
MINERU_BACKEND_CHOICES = [
    ("官方精准 API (Token, v4)", "online-api"),
    ("官方轻量 Agent API (免 Token, v1)", "online-agent"),
    ("本地/远程 vLLM HTTP", "http-client"),
    ("本机 Transformers", "transformers"),
]
MINERU_ONLINE_BACKENDS = {"online-api", "online-agent"}
MINERU_LOCAL_SETUP_HINT = """
> 本地/远程 MinerU 后端需要先准备运行服务。Windows 用户建议安装 Docker Desktop，
> 再按 MinerU 镜像向导启动服务，最后把 OpenAI-compatible 服务地址填到 `vLLM服务地址`。
>
> 向导：[Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/) |
> [MinerU 项目与 Docker 镜像说明](https://github.com/opendatalab/MinerU)
""".strip()
_mineru_backend_values = {value for _, value in MINERU_BACKEND_CHOICES}
mineru_default_backend = (
    settings.mineru.backend
    if settings.mineru.backend in MINERU_ONLINE_BACKENDS
    else "online-api"
)


def download_with_limit(url: str, save_path: str, size_limit: int = None) -> str:
    """
    This function downloads a file from a URL and saves it to a specified path.

    Inputs:
        - url: The URL to download the file from
        - save_path: The path to save the file to
        - size_limit: The maximum size of the file to download

    Returns:
        - The path of the downloaded file
    """
    chunk_size = 1024
    total_size = 0
    with requests.get(url, stream=True, timeout=10) as response:
        response.raise_for_status()
        content = response.headers.get("Content-Disposition")
        try:  # filename from header
            _, params = cgi.parse_header(content)
            filename = params["filename"]
        except Exception:  # filename from url
            filename = Path(url).name
        filename = Path(filename).stem + ".pdf"
        save_path = Path(save_path)
        file_path = save_path / filename
        with file_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=chunk_size):
                total_size += len(chunk)
                if size_limit and total_size > size_limit:
                    raise gr.Error("Exceeds file size limit")
                file.write(chunk)
    return file_path


def _prepare_input_file(
    file_type: str, file_input: str, link_input: str, output_dir: Path
) -> Path:
    """
    This function prepares the input file for translation.

    Inputs:
        - file_type: The type of file to translate (File or Link)
        - file_input: The path to the file to translate
        - link_input: The link to the file to translate
        - output_dir: The directory to save the file to

    Returns:
        - The path of the input file
    """
    if file_type == "File":
        if not file_input:
            raise gr.Error("No file input provided")
        file_path = shutil.copy(file_input, output_dir)
    else:
        if not link_input:
            raise gr.Error("No link input provided")
        try:
            # 对于链接，检查是否为Markdown文件
            if link_input.lower().endswith((".md", ".markdown")):
                # 下载Markdown文件
                file_path = download_with_limit(link_input, output_dir)
            else:
                # 下载PDF文件
                file_path = download_with_limit(link_input, output_dir)
        except Exception as e:
            raise gr.Error(f"Error downloading file: {e}") from e

    return Path(file_path)


def _pdf_text_layer_stats(file_path: Path, min_text_chars: int = 1) -> dict:
    stats = {
        "is_pdf": file_path.suffix.lower() == ".pdf",
        "pages": 0,
        "text_chars": 0,
        "is_textless": False,
        "error": None,
    }
    if not stats["is_pdf"]:
        return stats

    try:
        import pymupdf

        with pymupdf.open(file_path) as doc:
            stats["pages"] = len(doc)
            for page in doc:
                text = page.get_text("text") or ""
                stats["text_chars"] += len(re.sub(r"\s+", "", text))
                if stats["text_chars"] >= min_text_chars:
                    break
        stats["is_textless"] = (
            stats["pages"] > 0 and stats["text_chars"] < min_text_chars
        )
    except Exception as exc:
        stats["error"] = str(exc)
        logger.warning("PDF text-layer preflight failed for %s: %s", file_path, exc)
    return stats


def _is_babeldoc_textless_error(error: BaseException) -> bool:
    markers = (
        "The document contains no paragraphs",
        "文档中没有段落",
        "Scanned PDF detected",
    )
    seen = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        message = str(current)
        if any(marker in message for marker in markers):
            return True
        current = current.__cause__ or current.__context__
    return False


def _matches_output_name(path: Path, file_name: str) -> bool:
    return path.name == file_name or path.name.endswith(f"_{file_name}")


def _first_existing_output(
    paths: list[Path], file_names: list[str], allow_any_previewable: bool = False
) -> Path | None:
    for file_name in file_names:
        for path in paths:
            if _matches_output_name(path, file_name) and path.exists():
                return path
    if allow_any_previewable:
        for path in paths:
            if path.exists() and path.suffix.lower() in {".pdf", ".md", ".html"}:
                return path
    return None


def _render_mineru_markdown_preview_html(output_file_paths) -> str:
    if not output_file_paths:
        return "<p style='text-align:center; color:#999;'>未生成可预览文件</p>"
    paths = [Path(path) for path in output_file_paths]
    md_candidates = [
        path
        for path in paths
        if _matches_output_name(path, "translated_self_contained.md")
    ]
    md_candidates += [
        path for path in paths if _matches_output_name(path, "translated.md")
    ]
    md_candidates += [
        path
        for path in paths
        if _matches_output_name(path, "bilingual_self_contained.md")
    ]
    md_candidates += [
        path for path in paths if _matches_output_name(path, "bilingual.md")
    ]
    md_candidates += [path for path in paths if path.suffix.lower() == ".md"]
    html_candidates = [
        path for path in paths if _matches_output_name(path, "translated.html")
    ]
    html_candidates += [path for path in paths if path.suffix.lower() == ".html"]
    try:
        for path in md_candidates:
            if path.exists():
                content = path.read_text(encoding="utf-8")
                content = embed_markdown_images_as_data_uris(
                    content,
                    base_dirs=[path.parent, path.parent / "images"],
                )
                return MarkdownPreview.generate_single_html(content, title=path.name)
        for path in html_candidates:
            if path.exists():
                return path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.exception("MinerU Markdown preview render failed")
        return (
            f"<p style='color:#b42318;'>预览渲染失败: {html_lib.escape(str(exc))}</p>"
        )
    return (
        "<p style='text-align:center; color:#999;'>没有找到 Markdown/HTML 预览文件</p>"
    )


def _status_label(status: str | None) -> str:
    status_map = {
        "created": "已创建",
        "processing": "处理中",
        "complete": "完成",
        "completed": "完成",
        "failed": "失败",
    }
    return status_map.get(status or "", status or "-")


def _route_label(route: str) -> str:
    route_map = {
        "babeldoc": "BabelDOC",
        "mineru": "MinerU",
    }
    return route_map.get(route, route)


def _file_type_label(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "PDF"
    if suffix in {".md", ".markdown"}:
        return "Markdown"
    if suffix == ".html":
        return "HTML"
    if suffix == ".json":
        return "JSON"
    if suffix == ".csv":
        return "CSV"
    if suffix == ".txt":
        return "TXT"
    return suffix.lstrip(".").upper() or "文件"


def _history_file_icon(file_type: str) -> str:
    icon_map = {
        "PDF": "📄",
        "Markdown": "📝",
        "HTML": "🌐",
        "JSON": "{}",
        "CSV": "▦",
        "TXT": "TXT",
    }
    return icon_map.get(file_type, "▣")


def _format_history_time(value: str) -> str:
    if not value:
        return "-"
    try:
        return datetime.fromisoformat(str(value)).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return str(value).replace("T", " ")[:16]


def _history_choice_labels(rows: list[list[str]]) -> list[str]:
    labels = []
    for index, row in enumerate(rows, start=1):
        file_type = str(row[HISTORY_FILE_TYPE_INDEX])
        file_name = str(row[HISTORY_FILE_NAME_INDEX])
        route = str(row[1])
        created_at = _format_history_time(str(row[HISTORY_CREATED_AT_INDEX]))
        labels.append(
            f"{index:03d} {_history_file_icon(file_type)} {file_name} · {route} · {created_at}"
        )
    return labels


def _history_default_choice(rows: list[list[str]]) -> str | None:
    choices = _history_choice_labels(rows)
    return choices[0] if choices else None


def _history_dropdown_update(rows: list[list[str]]):
    choices = _history_choice_labels(rows)
    return gr.update(choices=choices, value=None)


def render_history_cards(rows: list[list[str]], max_items: int = 6) -> str:
    if not rows:
        return """
        <div class="history-empty">
            <div class="history-empty-title">暂无历史文件</div>
            <div class="history-empty-subtitle">完成翻译后，PDF 和 Markdown 文件会出现在这里。</div>
        </div>
        """

    items = []
    for row in rows[:max_items]:
        file_type = html_lib.escape(str(row[HISTORY_FILE_TYPE_INDEX]))
        file_name = html_lib.escape(str(row[HISTORY_FILE_NAME_INDEX]))
        source_file = html_lib.escape(str(row[2]))
        route = html_lib.escape(str(row[1]))
        status = html_lib.escape(str(row[6]))
        created_at = html_lib.escape(
            _format_history_time(str(row[HISTORY_CREATED_AT_INDEX]))
        )
        icon = html_lib.escape(_history_file_icon(str(row[HISTORY_FILE_TYPE_INDEX])))
        items.append(
            f"""
            <div class="history-card">
                <div class="history-card-icon">{icon}</div>
                <div class="history-card-main">
                    <div class="history-card-name">{file_name}</div>
                    <div class="history-card-meta">{route} · {file_type} · {created_at}</div>
                    <div class="history-card-source">{source_file}</div>
                </div>
                <div class="history-card-status">{status}</div>
            </div>
            """
        )
    return f"<div class='history-card-list'>{''.join(items)}</div>"


def refresh_babeldoc_history_picker():
    rows = refresh_babeldoc_history()
    return (
        _history_dropdown_update(rows),
        _history_dropdown_update(rows),
        rows,
        gr.update(value=None, visible=False),
    )


def refresh_mineru_history_picker():
    rows = refresh_mineru_history()
    return (
        _history_dropdown_update(rows),
        _history_dropdown_update(rows),
        rows,
        gr.update(value=None, visible=False),
    )


def _project_result_files(
    project_id: str, metadata: dict, route_filter: str | None = None
):
    project_dir = storage_manager.projects_dir / project_id
    result_routes = ["babeldoc", "mineru"]
    if route_filter in result_routes:
        result_routes = [route_filter]

    seen: set[Path] = set()
    results = metadata.get("results", {})
    for route in result_routes:
        for file_name in results.get(route, []):
            file_path = project_dir / route / file_name
            if (
                file_path.exists()
                and file_path.is_file()
                and file_path.suffix.lower() in HISTORY_VISIBLE_SUFFIXES
            ):
                seen.add(file_path.resolve())
                yield route, file_path

    for route in result_routes:
        route_dir = project_dir / route
        if not route_dir.exists():
            continue
        for file_path in sorted(route_dir.rglob("*")):
            if (
                not file_path.is_file()
                or file_path.suffix.lower() not in HISTORY_VISIBLE_SUFFIXES
            ):
                continue
            resolved = file_path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            yield route, file_path


def refresh_history_files(route_filter: str | None = None):
    """Return file-level history rows for the requested route."""
    rows = []
    try:
        for project in storage_manager.list_projects():
            project_id = project.get("project_id")
            if not project_id:
                continue
            try:
                metadata = storage_manager.get_project(project_id)
            except Exception:
                metadata = project
            for route, file_path in _project_result_files(
                project_id, metadata, route_filter
            ):
                rows.append(
                    [
                        project_id,
                        _route_label(route),
                        metadata.get("source_file", "-"),
                        _file_type_label(file_path),
                        file_path.name,
                        metadata.get("created_at", "-"),
                        _status_label(metadata.get("status")),
                        str(file_path),
                    ]
                )
    except Exception:
        logger.exception("Failed to refresh history files")
    return rows


def refresh_babeldoc_history():
    return refresh_history_files("babeldoc")


def refresh_mineru_history():
    return refresh_history_files("mineru")


def _history_rows_empty(history_rows) -> bool:
    if history_rows is None:
        return True
    if hasattr(history_rows, "empty"):
        return bool(history_rows.empty)
    try:
        return len(history_rows) == 0
    except TypeError:
        return True


def _history_row_from_event(history_rows, event: gr.SelectData | None):
    if _history_rows_empty(history_rows) or event is None:
        return None
    row_index = None
    event_index = getattr(event, "index", None)
    if isinstance(event_index, (list, tuple)) and event_index:
        row_index = event_index[0]
    elif isinstance(event_index, int):
        row_index = event_index

    if row_index is None:
        row_value = getattr(event, "row_value", None)
        return row_value

    try:
        if hasattr(history_rows, "iloc"):
            return list(history_rows.iloc[int(row_index)])
        return history_rows[int(row_index)]
    except Exception:
        logger.exception("Failed to read selected history row")
        return getattr(event, "row_value", None)


def _history_row_from_choice(history_rows, selected_choice: str | None):
    if _history_rows_empty(history_rows) or not selected_choice:
        return None
    iterable_rows = (
        history_rows.values.tolist()
        if hasattr(history_rows, "values")
        else history_rows
    )
    selected_label = str(selected_choice)
    for row, label in zip(
        iterable_rows, _history_choice_labels(iterable_rows), strict=False
    ):
        if str(label) == selected_label:
            return row

    try:
        choice_match = re.match(r"^\s*(\d+)", str(selected_choice))
        choice_index = int(choice_match.group(1)) - 1 if choice_match else -1
        history_length = len(history_rows)
        if 0 <= choice_index < history_length:
            if hasattr(history_rows, "iloc"):
                return list(history_rows.iloc[choice_index])
            return history_rows[choice_index]
    except (TypeError, ValueError, AttributeError):
        pass
    return None


def _history_delete_clear_outputs(
    rows: list[list[str]], message: str, is_error: bool = False
):
    color = "#b42318" if is_error else "#047857"
    return (
        _history_dropdown_update(rows),
        _history_dropdown_update(rows),
        rows,
        gr.update(value=None, visible=False),
        gr.update(value=None, visible=False),
        gr.update(
            value=f"<p style='color:#64748B;'>{html_lib.escape(message)}</p>",
            visible=True,
        ),
        gr.update(
            value=f"<span style='color:{color};'>{html_lib.escape(message)}</span>",
            visible=True,
        ),
    )


def delete_selected_history_file(
    history_rows, selected_choice: str | None, route_filter: str | None = None
):
    rows_after = refresh_history_files(route_filter)
    row = _history_row_from_choice(history_rows, selected_choice)
    if not row or len(row) <= HISTORY_FILE_PATH_INDEX:
        return _history_delete_clear_outputs(
            rows_after, "请先选择要删除的历史文件。", True
        )

    file_path = Path(str(row[HISTORY_FILE_PATH_INDEX]))
    try:
        resolved_file = file_path.resolve(strict=False)
        projects_root = storage_manager.projects_dir.resolve(strict=False)
        if (
            resolved_file.suffix.lower() not in HISTORY_VISIBLE_SUFFIXES
            or not resolved_file.is_relative_to(projects_root)
        ):
            return _history_delete_clear_outputs(
                rows_after, "只能删除历史目录里的 PDF 或 Markdown 文件。", True
            )
        if not resolved_file.exists() or not resolved_file.is_file():
            rows_after = refresh_history_files(route_filter)
            return _history_delete_clear_outputs(
                rows_after, "文件已不存在，列表已刷新。", True
            )

        display_name = resolved_file.name
        resolved_file.unlink()
        rows_after = refresh_history_files(route_filter)
        return _history_delete_clear_outputs(rows_after, f"已删除：{display_name}")
    except Exception as exc:
        logger.exception("Failed to delete selected history file")
        rows_after = refresh_history_files(route_filter)
        return _history_delete_clear_outputs(rows_after, f"删除失败：{exc}", True)


def delete_selected_babeldoc_history_file(history_rows, selected_choice: str | None):
    return delete_selected_history_file(history_rows, selected_choice, "babeldoc")


def delete_selected_mineru_history_file(history_rows, selected_choice: str | None):
    return delete_selected_history_file(history_rows, selected_choice, "mineru")


def _preview_history_row(row):
    if not row or len(row) <= HISTORY_FILE_PATH_INDEX:
        return (
            gr.update(),
            gr.update(
                value="<p style='color:#64748B;'>请选择一个历史文件</p>", visible=True
            ),
            gr.update(visible=False),
        )

    file_path = Path(str(row[HISTORY_FILE_PATH_INDEX]))
    if not file_path.exists():
        return (
            gr.update(),
            gr.update(
                value="<p style='color:#b42318;'>历史文件不存在，请刷新列表</p>",
                visible=True,
            ),
            gr.update(visible=False),
        )

    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return (
            gr.update(value=str(file_path), visible=True),
            gr.update(value="", visible=False),
            gr.update(value=str(file_path), visible=True),
        )

    try:
        if suffix in {".md", ".markdown"}:
            content = file_path.read_text(encoding="utf-8")
            content = embed_markdown_images_as_data_uris(
                content,
                base_dirs=[file_path.parent, file_path.parent / "images"],
            )
            html_content = MarkdownPreview.generate_single_html(
                content, title=file_path.name
            )
        elif suffix == ".html":
            html_content = file_path.read_text(encoding="utf-8")
        else:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            html_content = (
                "<pre style='white-space:pre-wrap; overflow:auto; padding:12px; "
                "border:1px solid #D8DEE9; border-radius:8px; background:#F8FAFC;'>"
                f"{html_lib.escape(content)}"
                "</pre>"
            )
    except Exception as exc:
        logger.exception("Failed to render history preview")
        html_content = (
            f"<p style='color:#b42318;'>预览失败: {html_lib.escape(str(exc))}</p>"
        )

    return (
        gr.update(value=None, visible=False),
        gr.update(value=html_content, visible=True),
        gr.update(value=str(file_path), visible=True),
    )


def preview_history_file(history_rows, event: gr.SelectData):
    return _preview_history_row(_history_row_from_event(history_rows, event))


def preview_selected_history_file(history_rows, selected_choice: str | None):
    return _preview_history_row(_history_row_from_choice(history_rows, selected_choice))


def preview_selected_history_file_only(history_rows, selected_choice: str | None):
    pdf_update, html_update, _download_update = preview_selected_history_file(
        history_rows,
        selected_choice,
    )
    return pdf_update, html_update


def selected_history_file_download(history_rows, selected_choice: str | None):
    row = _history_row_from_choice(history_rows, selected_choice)
    if not row or len(row) <= HISTORY_FILE_PATH_INDEX:
        return gr.update(value=None, visible=False)
    file_path = Path(str(row[HISTORY_FILE_PATH_INDEX]))
    if (
        not file_path.exists()
        or file_path.suffix.lower() not in HISTORY_VISIBLE_SUFFIXES
    ):
        return gr.update(value=None, visible=False)
    return gr.update(value=str(file_path), visible=True)


def _record_babeldoc_history(
    source_file: Path,
    mono_path: Path | None,
    dual_path: Path | None,
    glossary_path: Path | None,
    lang_from: str,
    lang_to: str,
) -> str | None:
    result_paths = [
        path for path in (mono_path, dual_path, glossary_path) if path and path.exists()
    ]
    if not result_paths:
        return None
    try:
        project_id = storage_manager.create_project(
            source_file,
            {
                "title": source_file.stem,
                "lang_in": lang_map.get(lang_from, lang_from),
                "lang_out": lang_map.get(lang_to, lang_to),
                "translation_path": "babeldoc",
                "output_formats": sorted(
                    {path.suffix.lower().lstrip(".") for path in result_paths}
                ),
            },
        )
        for result_path in result_paths:
            storage_manager.save_result(
                project_id,
                "babeldoc",
                result_path.name,
                result_path.read_bytes(),
            )
        storage_manager.update_project_status(project_id, "completed")
        return project_id
    except Exception:
        logger.exception("Failed to record BabelDOC history")
        return None


def _sync_legacy_history_to_output():
    if Path(history_storage_root) != Path("output"):
        return
    legacy_projects = Path("storage") / "projects"
    if not legacy_projects.exists():
        return

    allowed_suffixes = {".pdf", ".md", ".markdown", ".html", ".json", ".csv", ".txt"}
    for legacy_project_dir in legacy_projects.iterdir():
        if not legacy_project_dir.is_dir():
            continue
        project_id = legacy_project_dir.name
        target_project_dir = storage_manager.projects_dir / project_id
        if target_project_dir.exists():
            continue
        metadata_file = legacy_project_dir / "metadata.json"
        if not metadata_file.exists():
            continue
        try:
            metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        except Exception:
            logger.exception(
                "Failed to read legacy project metadata: %s", metadata_file
            )
            continue

        target_project_dir.mkdir(parents=True, exist_ok=True)
        for source_candidate in legacy_project_dir.glob("source.*"):
            if source_candidate.is_file():
                shutil.copy2(
                    source_candidate, target_project_dir / source_candidate.name
                )

        for route in ("babeldoc", "mineru"):
            source_route_dir = legacy_project_dir / route
            if not source_route_dir.exists():
                continue
            target_route_dir = target_project_dir / route
            target_route_dir.mkdir(parents=True, exist_ok=True)
            for file_path in source_route_dir.rglob("*"):
                if not file_path.is_file():
                    continue
                relative_path = file_path.relative_to(source_route_dir)
                if relative_path.parts and relative_path.parts[0] == "images":
                    pass
                elif file_path.suffix.lower() not in allowed_suffixes:
                    continue
                target_file_path = target_route_dir / relative_path
                target_file_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, target_file_path)

        now_text = datetime.now().isoformat()
        metadata.setdefault("project_id", project_id)
        metadata.setdefault("title", metadata.get("source_file", project_id))
        metadata.setdefault("created_at", now_text)
        metadata.setdefault("updated_at", metadata.get("created_at", now_text))
        metadata.setdefault("status", "completed")
        metadata.setdefault("lang_in", "en")
        metadata.setdefault("lang_out", "zh")
        metadata.setdefault("translation_path", "mineru")
        metadata.setdefault("source_file", "source.pdf")
        storage_manager._save_metadata(project_id, metadata)
        storage_manager._update_index(project_id, metadata)


def _validate_rate_limit_inputs(
    true_rate_limit_mode: str, **inputs
) -> tuple[bool, str]:
    """
    Validate rate limit inputs

    Returns:
        tuple: (is_valid, error_message)
    """
    if true_rate_limit_mode == "RPM":
        rpm = inputs.get("rpm_input", 0)
        if not isinstance(rpm, int | float) or rpm <= 0:
            return False, "RPM must be a positive integer"

        if isinstance(rpm, float):
            if not rpm.is_integer():
                return False, "RPM must be a positive integer"

    elif true_rate_limit_mode == "Concurrent Threads":
        threads = inputs.get("concurrent_threads", 0)
        if not isinstance(threads, int | float) or threads <= 0:
            return False, "Concurrent threads must be a positive integer"

        if isinstance(threads, float):
            if not threads.is_integer():
                return False, "Concurrent threads must be a positive integer"

    elif true_rate_limit_mode == "Custom":
        qps = inputs.get("custom_qps", 0)
        pool_workers = inputs.get("custom_pool_workers")

        if not isinstance(qps, int | float) or qps <= 0:
            return False, "QPS must be a positive integer"

        if isinstance(qps, float):
            if not qps.is_integer():
                return False, "QPS must be a positive integer"

        if pool_workers is not None and (
            not isinstance(pool_workers, int | float) or pool_workers < 0
        ):
            return False, "Pool workers must be a non-negative integer"

        if isinstance(pool_workers, float):
            if not pool_workers.is_integer():
                return False, "Pool workers must be a non-negative integer"

    return True, ""


def _calculate_rate_limit_params(
    rate_limit_mode: str, ui_inputs: dict, default_qps: int = 4
) -> tuple[int, int | None]:
    """
    Calculate QPS and pool workers based on rate limit mode

    Args:
        rate_limit_mode: Rate limit mode ("RPM", "Concurrent Threads", "Custom")
        ui_inputs: User input parameters dictionary
        default_qps: Default QPS value

    Returns:
        tuple: (qps, pool_max_workers)

    Raises:
        ValueError: When input parameter validation fails
    """
    # Validate input parameters
    is_valid, error_msg = _validate_rate_limit_inputs(
        true_rate_limit_mode=rate_limit_mode, **ui_inputs
    )
    if not is_valid:
        logger.warning(f"Rate limit validation failed: {error_msg}")
        raise ValueError(error_msg)

    if rate_limit_mode == "RPM":
        rpm: int = ui_inputs.get("rpm_input", 240)
        qps = max(1, rpm // 60)
        pool_workers = min(1000, qps * 10)

    elif rate_limit_mode == "Concurrent Threads":
        threads: int = ui_inputs.get("concurrent_threads_input", 40)
        # Ensure at least 1 worker, at most 1000 workers, using a safer calculation method
        pool_workers = min(1000, max(1, min(int(threads * 0.9), max(1, threads - 20))))
        qps = max(1, pool_workers)

    else:  # Custom
        qps = ui_inputs.get("custom_qps_input", default_qps)
        pool_workers = ui_inputs.get("custom_pool_workers")
        qps = int(qps)
        pool_workers = int(pool_workers) if pool_workers and pool_workers > 0 else None

    logger.info(f"QPS: {qps}, Pool Workers: {pool_workers}")

    return qps, pool_workers if pool_workers and pool_workers > 0 else None


def _build_translate_settings(
    base_settings: CLIEnvSettingsModel,
    file_path: Path,
    output_dir: Path,
    ui_inputs: dict,
) -> SettingsModel:
    """
    This function builds translation settings from UI inputs.

    Inputs:
        - base_settings: The base settings model to build upon
        - file_path: The path to the input file
        - output_dir: The output directory
        - ui_inputs: A dictionary of UI inputs

    Returns:
        - A configured SettingsModel instance
    """
    # Clone base settings to avoid modifying the original
    translate_settings = base_settings.clone()
    original_output = translate_settings.translation.output
    original_pages = translate_settings.pdf.pages
    original_gui_settings = (
        config_manager.config_cli_settings.gui_settings
        if config_manager.config_cli_settings
        else translate_settings.gui_settings
    )

    # Extract UI values
    service = ui_inputs.get("service")
    lang_from = ui_inputs.get("lang_from")
    lang_to = ui_inputs.get("lang_to")
    page_range = ui_inputs.get("page_range")
    page_input = ui_inputs.get("page_input")
    prompt = ui_inputs.get("prompt")
    ignore_cache = ui_inputs.get("ignore_cache")

    # PDF Output Options
    no_mono = ui_inputs.get("no_mono")
    no_dual = ui_inputs.get("no_dual")
    dual_translate_first = ui_inputs.get("dual_translate_first")
    use_alternating_pages_dual = ui_inputs.get("use_alternating_pages_dual")
    watermark_output_mode = ui_inputs.get("watermark_output_mode")

    # Rate Limit Options
    rate_limit_mode = ui_inputs.get("rate_limit_mode")

    # Advanced Translation Options
    min_text_length = ui_inputs.get("min_text_length")
    rpc_doclayout = ui_inputs.get("rpc_doclayout")
    no_auto_extract_glossary = ui_inputs.get("no_auto_extract_glossary")
    primary_font_family = ui_inputs.get("primary_font_family")

    # Advanced PDF Options
    skip_clean = ui_inputs.get("skip_clean")
    disable_rich_text_translate = ui_inputs.get("disable_rich_text_translate")
    enhance_compatibility = ui_inputs.get("enhance_compatibility")
    split_short_lines = ui_inputs.get("split_short_lines")
    short_line_split_factor = ui_inputs.get("short_line_split_factor")
    translate_table_text = ui_inputs.get("translate_table_text")
    skip_scanned_detection = ui_inputs.get("skip_scanned_detection")
    ocr_workaround = ui_inputs.get("ocr_workaround")
    max_pages_per_part = ui_inputs.get("max_pages_per_part")
    formular_font_pattern = ui_inputs.get("formular_font_pattern")
    formular_char_pattern = ui_inputs.get("formular_char_pattern")
    auto_enable_ocr_workaround = ui_inputs.get("auto_enable_ocr_workaround")
    only_include_translated_page = ui_inputs.get("only_include_translated_page")

    # BabelDOC v0.5.1 new options
    merge_alternating_line_numbers = ui_inputs.get("merge_alternating_line_numbers")
    remove_non_formula_lines = ui_inputs.get("remove_non_formula_lines")
    non_formula_line_iou_threshold = ui_inputs.get("non_formula_line_iou_threshold")
    figure_table_protection_threshold = ui_inputs.get(
        "figure_table_protection_threshold"
    )
    skip_formula_offset_calculation = ui_inputs.get("skip_formula_offset_calculation")

    # New input for custom_system_prompt
    custom_system_prompt_input = ui_inputs.get("custom_system_prompt_input")
    glossaries = ui_inputs.get("glossaries")
    save_auto_extracted_glossary = ui_inputs.get("save_auto_extracted_glossary")

    # Map UI language selections to language codes
    source_lang = lang_map.get(lang_from, "auto")
    target_lang = lang_map.get(lang_to, "zh")

    # Set up page selection
    if page_range == "Range" and page_input:
        pages = page_input  # The backend parser handles the format
    else:
        # Use predefined ranges from page_map
        selected_pages = page_map[page_range]
        if selected_pages is None:
            pages = None  # All pages
        else:
            # Convert page indices to comma-separated string
            pages = ",".join(
                str(p + 1) for p in selected_pages
            )  # +1 because UI is 1-indexed

    # Update settings with UI values
    translate_settings.basic.input_files = {str(file_path)}
    translate_settings.report_interval = 0.2
    translate_settings.translation.lang_in = source_lang
    translate_settings.translation.lang_out = target_lang
    translate_settings.translation.output = str(output_dir)
    translate_settings.translation.ignore_cache = ignore_cache

    # Update Translation Settings
    if min_text_length is not None:
        translate_settings.translation.min_text_length = int(min_text_length)
    if rpc_doclayout:
        translate_settings.translation.rpc_doclayout = rpc_doclayout
    translate_settings.translation.no_auto_extract_glossary = no_auto_extract_glossary
    if primary_font_family:
        if primary_font_family == "Auto":
            translate_settings.translation.primary_font_family = None
        else:
            translate_settings.translation.primary_font_family = primary_font_family

    # Calculate and update rate limit settings
    if service != "SiliconFlowFree":
        qps, pool_workers = _calculate_rate_limit_params(
            rate_limit_mode, ui_inputs, translate_settings.translation.qps or 4
        )

        # Update translation settings
        translate_settings.translation.qps = int(qps)
        translate_settings.translation.pool_max_workers = (
            int(pool_workers) if pool_workers is not None else None
        )

    # Update PDF Settings
    translate_settings.pdf.pages = pages
    translate_settings.pdf.no_mono = no_mono
    translate_settings.pdf.no_dual = no_dual
    translate_settings.pdf.dual_translate_first = dual_translate_first
    translate_settings.pdf.use_alternating_pages_dual = use_alternating_pages_dual

    # Map watermark mode from UI to enum
    if watermark_output_mode == "Watermarked":
        from pdf2zh_next.config.model import WatermarkOutputMode

        translate_settings.pdf.watermark_output_mode = WatermarkOutputMode.Watermarked
    elif watermark_output_mode == "No Watermark":
        from pdf2zh_next.config.model import WatermarkOutputMode

        translate_settings.pdf.watermark_output_mode = WatermarkOutputMode.NoWatermark

    # Update Advanced PDF Settings
    translate_settings.pdf.skip_clean = skip_clean
    translate_settings.pdf.disable_rich_text_translate = disable_rich_text_translate
    translate_settings.pdf.enhance_compatibility = enhance_compatibility
    translate_settings.pdf.split_short_lines = split_short_lines
    translate_settings.pdf.ocr_workaround = ocr_workaround
    if short_line_split_factor is not None:
        translate_settings.pdf.short_line_split_factor = float(short_line_split_factor)

    translate_settings.pdf.translate_table_text = translate_table_text
    translate_settings.pdf.skip_scanned_detection = skip_scanned_detection
    translate_settings.pdf.auto_enable_ocr_workaround = auto_enable_ocr_workaround
    translate_settings.pdf.only_include_translated_page = only_include_translated_page

    if max_pages_per_part is not None and max_pages_per_part > 0:
        translate_settings.pdf.max_pages_per_part = int(max_pages_per_part)

    if formular_font_pattern:
        translate_settings.pdf.formular_font_pattern = formular_font_pattern

    if formular_char_pattern:
        translate_settings.pdf.formular_char_pattern = formular_char_pattern

    # Apply BabelDOC v0.5.1 new options
    translate_settings.pdf.no_merge_alternating_line_numbers = (
        not merge_alternating_line_numbers
    )
    translate_settings.pdf.no_remove_non_formula_lines = not remove_non_formula_lines
    if non_formula_line_iou_threshold is not None:
        translate_settings.pdf.non_formula_line_iou_threshold = float(
            non_formula_line_iou_threshold
        )
    if figure_table_protection_threshold is not None:
        translate_settings.pdf.figure_table_protection_threshold = float(
            figure_table_protection_threshold
        )
    translate_settings.pdf.skip_formula_offset_calculation = (
        skip_formula_offset_calculation
    )

    assert service in TRANSLATION_ENGINE_METADATA_MAP, "UNKNOW TRANSLATION ENGINE!"

    for metadata in TRANSLATION_ENGINE_METADATA:
        cli_flag = metadata.cli_flag_name
        setattr(translate_settings, cli_flag, False)

    metadata = TRANSLATION_ENGINE_METADATA_MAP[service]
    cli_flag = metadata.cli_flag_name
    setattr(translate_settings, cli_flag, True)
    if metadata.cli_detail_field_name:
        detail_setting = getattr(translate_settings, metadata.cli_detail_field_name)
        if metadata.setting_model_type:
            for field_name in metadata.setting_model_type.model_fields:
                if field_name == "translate_engine_type" or field_name == "support_llm":
                    continue
                if disable_gui_sensitive_input:
                    if field_name in GUI_PASSWORD_FIELDS:
                        continue
                    if field_name in GUI_SENSITIVE_FIELDS:
                        continue
                value = ui_inputs.get(field_name)
                if _should_preserve_blank_engine_field(field_name, value):
                    continue
                type_hint = detail_setting.model_fields[field_name].annotation
                original_type = typing.get_origin(type_hint)
                type_args = typing.get_args(type_hint)
                if type_hint is str or str in type_args:
                    pass
                elif type_hint is int or int in type_args:
                    value = int(value)
                elif type_hint is bool or bool in type_args:
                    value = bool(value)
                else:
                    raise Exception(
                        f"Unsupported type {type_hint} for field {field_name} in gui translation engine settings"
                    )
                setattr(detail_setting, field_name, value)

    # Add custom prompt if provided
    if prompt:
        # This might need adjustment based on how prompt is handled in the new system
        translate_settings.custom_prompt = Template(prompt)

    # Add custom system prompt if provided
    if custom_system_prompt_input:
        translate_settings.translation.custom_system_prompt = custom_system_prompt_input
    else:
        translate_settings.translation.custom_system_prompt = None

    if glossaries:
        translate_settings.translation.glossaries = glossaries
    else:
        translate_settings.translation.glossaries = None

    translate_settings.translation.save_auto_extracted_glossary = (
        save_auto_extracted_glossary
    )

    # Validate settings before proceeding
    try:
        translate_settings.validate_settings()
        settings = translate_settings.to_settings_model()
        translate_settings.translation.output = original_output
        translate_settings.pdf.pages = original_pages
        translate_settings.gui_settings = original_gui_settings
        translate_settings.basic.gui = False
        translate_settings.basic.debug = False
        translate_settings.translation.glossaries = None
        if not settings.gui_settings.disable_config_auto_save:
            config_manager.write_user_default_config_file(settings=translate_settings)
        settings.validate_settings()
        return settings
    except ValueError as e:
        raise gr.Error(f"Invalid settings: {e}") from e


def _build_glossary_list(glossary_file, service_name=None):
    if not LLM_support_index_map.get(service_name, False):
        return None
    glossary_list = []
    if glossary_file is None:
        return None
    for file in glossary_file:
        try:
            f = io.StringIO(file.decode(chardet.detect(file)["encoding"]))
            with tempfile.NamedTemporaryFile(
                mode="w", delete=False, suffix=".csv"
            ) as temp_file:
                temp_file.write(f.getvalue())
                f.close()
            glossary_list.append(temp_file.name)
        except (UnicodeDecodeError, csv.Error, KeyError) as e:
            logger.error(f"Error processing glossary file: {e}")
            gr.Error(f"Failed to process glossary file: {e}")
    return ",".join(glossary_list)


async def _run_translation_task(
    settings: SettingsModel, file_path: Path, state: dict, progress: gr.Progress
) -> tuple[Path | None, Path | None, Path | None]:
    """
    This function runs the translation task and handles progress updates.

    Inputs:
        - settings: The translation settings
        - file_path: The path to the input file
        - state: The state dictionary for tracking the task
        - progress: The Gradio progress bar

    Returns:
        - A tuple of (mono_pdf_path, dual_pdf_path)
    """
    mono_path = None
    dual_path = None
    glossary_path = None
    first_progress_event = asyncio.Event()
    finished_event = asyncio.Event()
    last_progress_value = 0.1
    last_progress_desc = "正在启动 BabelDOC 翻译引擎..."
    last_event_time = time.monotonic()

    async def progress_heartbeat() -> None:
        start_time = time.monotonic()
        while not finished_event.is_set():
            await asyncio.sleep(5)
            if finished_event.is_set():
                break
            elapsed = int(time.monotonic() - start_time)
            if first_progress_event.is_set():
                wait_time = int(time.monotonic() - last_event_time)
                desc = f"{last_progress_desc}，已等待新进度 {wait_time} 秒"
                progress(last_progress_value, desc=desc)
            else:
                pending_value = min(0.18, 0.1 + elapsed / 600)
                progress(
                    pending_value,
                    desc=f"正在加载文档解析与翻译引擎，已等待 {elapsed} 秒...",
                )

    try:
        progress(last_progress_value, desc=last_progress_desc)
        heartbeat_task = asyncio.create_task(progress_heartbeat())
        settings.basic.input_files = set()
        async for event in do_translate_async_stream(settings, file_path):
            if event["type"] in (
                "progress_start",
                "progress_update",
                "progress_end",
            ):
                # Update progress bar
                desc = event["stage"]
                progress_value = 0.1 + event["overall_progress"] / 100.0 * 0.88
                part_index = event["part_index"]
                total_parts = event["total_parts"]
                stage_current = event["stage_current"]
                stage_total = event["stage_total"]
                desc = f"{desc} ({part_index}/{total_parts}, {stage_current}/{stage_total})"
                logger.info(f"Progress: {progress_value}, {desc}")
                first_progress_event.set()
                last_progress_value = min(progress_value, 0.98)
                last_progress_desc = desc
                last_event_time = time.monotonic()
                progress(progress_value, desc=desc)
            elif event["type"] == "finish":
                # Extract result paths
                result = event["translate_result"]
                mono_path = result.mono_pdf_path
                dual_path = result.dual_pdf_path
                glossary_path = result.auto_extracted_glossary_path
                finished_event.set()
                progress(1.0, desc="Translation complete!")
                break
            elif event["type"] == "error":
                # Handle error event
                error_msg = event.get("error", "Unknown error")
                error_details = event.get("details", "")
                # error_str = f"{error_msg}" + (
                #     f": {error_details}" if error_details else ""
                # )
                raise gr.Error(f"Translation error: {error_msg}")
    except asyncio.CancelledError:
        # Handle task cancellation - let translate_file handle the UI updates
        logger.info(
            f"Translation for session {state.get('session_id', 'unknown')} was cancelled"
        )
        raise  # Re-raise for the calling function to handle
    except TranslationError as e:
        # Handle structured translation errors
        logger.error(f"Translation error: {e}")
        raise gr.Error(f"Translation error: {e}") from e
    except gr.Error as e:
        # Handle Gradio errors
        logger.error(f"Gradio error: {e}")
        raise
    except Exception as e:
        # Handle other exceptions
        logger.error(f"Error in _run_translation_task: {e}", exc_info=True)
        raise gr.Error(f"Translation failed: {e}") from e
    finally:
        finished_event.set()
        if "heartbeat_task" in locals():
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass

    return mono_path, dual_path, glossary_path


async def _run_mineru_scan_fallback(
    settings: SettingsModel,
    file_path: Path,
    lang_from: str,
    lang_to: str,
    progress: gr.Progress,
    reason: str,
):
    backend = settings.mineru.backend or "online-api"
    if backend == "online-api" and not (
        settings.mineru.api_token or os.getenv("MINERU_API_TOKEN")
    ):
        raise gr.Error(
            "检测到纯扫描 PDF，BabelDOC 没有可翻译的文本层。"
            "请先在“扫描PDF翻译 (MinerU)”页填写 MinerU Token，"
            "或把 MinerU 后端切换为本地/远程 vLLM HTTP 后再重试。"
        )

    progress(0.02, desc="检测到纯扫描 PDF，自动切换 MinerU OCR...")
    fallback_settings = settings.model_copy(deep=True)
    fallback_settings.mineru.enabled = True
    fallback_settings.pdf.translation_path = "mineru"

    project_id = storage_manager.create_project(
        file_path,
        {
            "title": file_path.stem,
            "lang_in": fallback_settings.translation.lang_in,
            "lang_out": fallback_settings.translation.lang_out,
            "translation_path": "mineru",
            "fallback_from": "babeldoc",
            "fallback_reason": reason,
            "output_formats": ["Both"],
        },
    )

    try:
        pipeline = MinerUOptimizedPipeline(
            fallback_settings,
            storage_manager,
            project_id,
        )
        async for event in pipeline.process_pdf(file_path):
            stage = event.get("stage", "MinerU OCR")
            message = event.get("message") or "处理中"
            progress_value = float(event.get("progress") or 0.0)
            progress(progress_value, desc=f"MinerU OCR: {message}")
            if stage == "error":
                raise RuntimeError(message)

        metadata = storage_manager.get_project(project_id)
        mineru_files = metadata.get("results", {}).get("mineru", [])
        output_file_paths: list[Path] = []
        for file_name in mineru_files:
            output_path = storage_manager.get_file_path(
                project_id, f"mineru/{file_name}"
            )
            if output_path.exists():
                output_file_paths.append(output_path)

        if not output_file_paths:
            raise RuntimeError("MinerU OCR 未生成输出文件")

        translated_pdf = _first_existing_output(output_file_paths, ["translated.pdf"])
        mono_path = translated_pdf or _first_existing_output(
            output_file_paths,
            ["translated_self_contained.md", "translated.md", "translated.html"],
            allow_any_previewable=True,
        )
        dual_path = _first_existing_output(
            output_file_paths,
            ["bilingual_self_contained.md", "bilingual.md", "bilingual.html"],
        )
        html_preview = None
        if translated_pdf is None:
            html_preview = _render_mineru_markdown_preview_html(output_file_paths)

        storage_manager.update_project_status(project_id, "completed")
        gr.Info("BabelDOC 未检测到文本层，已自动改用 MinerU OCR 完成扫描 PDF 翻译。")
        progress(1.0, desc="MinerU OCR 翻译完成")

        return (
            str(mono_path) if mono_path else None,
            str(translated_pdf) if translated_pdf else None,
            html_preview,
            str(dual_path) if dual_path else None,
            None,
            gr.update(visible=bool(mono_path)),
            gr.update(visible=bool(dual_path)),
            gr.update(visible=False),
            gr.update(visible=bool(mono_path or dual_path)),
            gr.update(visible=bool(translated_pdf)),
            gr.update(visible=bool(html_preview)),
        )
    except gr.Error:
        storage_manager.update_project_status(project_id, "failed")
        raise
    except Exception as exc:
        storage_manager.update_project_status(project_id, "failed", error=str(exc))
        logger.exception("MinerU OCR fallback failed")
        raise gr.Error(
            "检测到纯扫描 PDF，BabelDOC 没有可翻译的文本层；"
            f"已尝试切换 MinerU OCR，但处理失败：{exc}"
        ) from exc


async def stop_translate_file(state: dict) -> None:
    """
    This function stops the translation process.

    Inputs:
        - state: The state of the translation process

    Returns:- None
    """
    if "current_task" not in state or state["current_task"] is None:
        return

    logger.info(
        f"Stopping translation for session {state.get('session_id', 'unknown')}"
    )
    # Cancel the task
    try:
        state["current_task"].cancel()
        # Wait briefly for cancellation to take effect
        await asyncio.sleep(0.1)
    except Exception as e:
        logger.error(f"Error stopping translation: {e}")
    finally:
        state["current_task"] = None


async def translate_file(
    file_type,
    file_input,
    link_input,
    service,
    lang_from,
    lang_to,
    page_range,
    page_input,
    # PDF Output Options
    no_mono,
    no_dual,
    dual_translate_first,
    use_alternating_pages_dual,
    watermark_output_mode,
    # Rate Limit Mode
    rate_limit_mode,
    rpm_input,
    concurrent_threads,
    custom_qps,
    custom_pool_workers,
    # Advanced Options
    prompt,
    min_text_length,
    rpc_doclayout,
    # New input for custom_system_prompt
    custom_system_prompt_input,
    glossary_file,
    save_auto_extracted_glossary,
    # New advanced translation options
    no_auto_extract_glossary,
    primary_font_family,
    skip_clean,
    disable_rich_text_translate,
    enhance_compatibility,
    split_short_lines,
    short_line_split_factor,
    translate_table_text,
    skip_scanned_detection,
    max_pages_per_part,
    formular_font_pattern,
    formular_char_pattern,
    ignore_cache,
    state,
    ocr_workaround,
    auto_enable_ocr_workaround,
    only_include_translated_page,
    # BabelDOC v0.5.1 new options
    merge_alternating_line_numbers,
    remove_non_formula_lines,
    non_formula_line_iou_threshold,
    figure_table_protection_threshold,
    skip_formula_offset_calculation,
    *translation_engine_arg_inputs,
    progress=None,
):
    """
    This function translates a PDF file from one language to another using the new architecture.

    Inputs:
        - file_type: The type of file to translate
        - file_input: The file to translate
        - link_input: The link to the file to translate
        - service: The translation service to use
        - lang_from: The language to translate from
        - lang_to: The language to translate to
        - page_range: The range of pages to translate
        - page_input: The input for the page range
        - prompt: The custom prompt for the llm
        - threads: The number of threads to use
        - skip_clean: Whether to skip subsetting fonts
        - ignore_cache: Whether to ignore the translation cache
        - state: The state of the translation process
        - translation_engine_arg_inputs: The translator engine args
        - progress: The progress bar

    Returns:
        - The translated mono PDF file
        - The preview PDF file
        - The translated dual PDF file
        - The visibility state of the mono PDF output
        - The visibility state of the dual PDF output
        - The visibility state of the output title
    """
    # Setup progress tracking
    if progress is None:
        progress = gr.Progress()

    # Initialize session and output directory
    session_id = str(uuid.uuid4())
    state["session_id"] = session_id

    # Track progress
    progress(0.01, desc="正在准备翻译任务...")

    # Prepare output directory
    output_dir = OUTPUT_ROOT / "sessions" / session_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collection of UI inputs for config building
    ui_inputs = {
        "service": service,
        "lang_from": lang_from,
        "lang_to": lang_to,
        "page_range": page_range,
        "page_input": page_input,
        # PDF Output Options
        "no_mono": no_mono,
        "no_dual": no_dual,
        "dual_translate_first": dual_translate_first,
        "use_alternating_pages_dual": use_alternating_pages_dual,
        "watermark_output_mode": watermark_output_mode,
        # Rate Limit Options
        "rate_limit_mode": rate_limit_mode,
        "rpm_input": rpm_input,
        "concurrent_threads": concurrent_threads,
        "custom_qps": custom_qps,
        "custom_pool_workers": custom_pool_workers,
        # Advanced Options
        "prompt": prompt,
        "min_text_length": min_text_length,
        "rpc_doclayout": rpc_doclayout,
        "custom_system_prompt_input": custom_system_prompt_input,
        "glossaries": _build_glossary_list(glossary_file, service),
        "save_auto_extracted_glossary": save_auto_extracted_glossary,
        # New advanced translation options
        "no_auto_extract_glossary": no_auto_extract_glossary,
        "primary_font_family": primary_font_family,
        "skip_clean": skip_clean,
        "disable_rich_text_translate": disable_rich_text_translate,
        "enhance_compatibility": enhance_compatibility,
        "split_short_lines": split_short_lines,
        "short_line_split_factor": short_line_split_factor,
        "translate_table_text": translate_table_text,
        "skip_scanned_detection": skip_scanned_detection,
        "max_pages_per_part": max_pages_per_part,
        "formular_font_pattern": formular_font_pattern,
        "formular_char_pattern": formular_char_pattern,
        "ignore_cache": ignore_cache,
        "ocr_workaround": ocr_workaround,
        "auto_enable_ocr_workaround": auto_enable_ocr_workaround,
        "only_include_translated_page": only_include_translated_page,
        # BabelDOC v0.5.1 new options
        "merge_alternating_line_numbers": merge_alternating_line_numbers,
        "remove_non_formula_lines": remove_non_formula_lines,
        "non_formula_line_iou_threshold": non_formula_line_iou_threshold,
        "figure_table_protection_threshold": figure_table_protection_threshold,
        "skip_formula_offset_calculation": skip_formula_offset_calculation,
    }
    for arg_name, arg_input in zip(
        __gui_service_arg_names, translation_engine_arg_inputs, strict=False
    ):
        ui_inputs[arg_name] = arg_input
    try:
        # Step 1: Prepare input file
        progress(0.02, desc="正在读取文件...")
        file_path = _prepare_input_file(file_type, file_input, link_input, output_dir)

        # 检查文件类型，如果是Markdown文件则使用专门的翻译函数
        if file_path.suffix.lower() in [".md", ".markdown"]:
            try:
                # Markdown文件智能翻译
                progress(0.05, desc="开始智能翻译Markdown文件...")
                logger.info(f"开始智能翻译Markdown文件: {file_path}")

                # 构建翻译设置
                translate_settings = _build_translate_settings(
                    _initialize_cli_config_for_gui_editing(),
                    file_path,
                    output_dir,
                    ui_inputs,
                )
                logger.info(
                    f"翻译设置构建完成: 从 {translate_settings.translation.lang_in} 到 {translate_settings.translation.lang_out}"
                )

                # 读取原文内容
                original_content = file_path.read_text(encoding="utf-8")

                # 调用智能Markdown翻译函数
                translated_content = await translate_markdown_smart(
                    file_path, translate_settings, progress
                )

                # 保存翻译结果
                output_file = output_dir / f"{file_path.stem}_translated.md"
                output_file.write_text(translated_content, encoding="utf-8")
                logger.info(f"翻译结果已保存到: {output_file}")

                # 生成预览HTML文件
                preview_file = MarkdownPreview.save_preview_file(
                    original_content,
                    translated_content,
                    output_file,
                    title=f"Markdown Translation - {file_path.name}",
                )

                progress(1.0, desc="Markdown翻译完成!")

                # 读取预览HTML内容
                preview_html_content = preview_file.read_text(encoding="utf-8")

                # 返回结果（包含预览文件）
                return (
                    str(output_file),  # Output mono file (翻译后的Markdown)
                    None,  # PDF Preview (Markdown不使用PDF预览)
                    preview_html_content,  # HTML Preview (HTML预览内容)
                    None,  # Output dual file (Markdown不支持双语输出)
                    None,  # Glossary file
                    gr.update(visible=True),  # Show mono download
                    gr.update(visible=False),  # Hide dual download
                    gr.update(visible=False),  # Hide glossary download
                    gr.update(visible=True),  # Show output title
                    gr.update(visible=False),  # Hide PDF preview
                    gr.update(visible=True),  # Show HTML preview
                )
            except Exception as e:
                logger.error(f"Markdown翻译失败: {e}")
                import traceback

                logger.error(f"详细错误信息: {traceback.format_exc()}")

                # 创建错误信息文件
                error_file = output_dir / f"{file_path.stem}_error.txt"
                error_content = f"Markdown翻译失败\n\n错误信息: {str(e)}\n\n详细信息:\n{traceback.format_exc()}"
                error_file.write_text(error_content, encoding="utf-8")

                # 创建错误预览HTML
                error_html = f"""
                <div style="padding: 20px; font-family: Arial, sans-serif;">
                    <h3 style="color: red;">❌ Markdown翻译失败</h3>
                    <div style="background: #f8d7da; color: #721c24; padding: 15px; border-radius: 5px; margin: 10px 0;">
                        <strong>错误信息:</strong> {str(e)}
                    </div>
                    <p>详细错误信息已保存到文件中，请下载查看。</p>
                </div>
                """

                # 返回错误状态
                return (
                    str(error_file),  # 返回错误文件路径
                    None,  # PDF Preview
                    error_html,  # HTML Preview (错误信息)
                    None,
                    None,
                    gr.update(visible=True),
                    gr.update(visible=False),
                    gr.update(visible=False),
                    gr.update(visible=True),
                    gr.update(visible=False),  # Hide PDF preview
                    gr.update(visible=True),  # Show HTML preview
                )
        else:
            # PDF文件翻译（原有逻辑）
            # Step 2: Build translation settings
            progress(0.04, desc="正在读取翻译设置...")
            translate_settings = _build_translate_settings(
                _initialize_cli_config_for_gui_editing(),
                file_path,
                output_dir,
                ui_inputs,
            )

            progress(0.07, desc="正在检查 PDF 文本层...")
            text_stats = _pdf_text_layer_stats(file_path)
            if text_stats["is_textless"]:
                logger.info(
                    "BabelDOC input has no extractable text layer, using MinerU fallback: %s",
                    text_stats,
                )
                return await _run_mineru_scan_fallback(
                    translate_settings,
                    file_path,
                    lang_from,
                    lang_to,
                    progress,
                    "pdf_text_layer_empty",
                )

            # Step 3: Create and run the translation task
            progress(0.1, desc="正在启动 BabelDOC 翻译引擎...")
            task = asyncio.create_task(
                _run_translation_task(translate_settings, file_path, state, progress)
            )
            state["current_task"] = task

            # Wait for the translation to complete
            try:
                mono_path, dual_path, glossary_path = await task
            except gr.Error as error:
                if _is_babeldoc_textless_error(error):
                    logger.info(
                        "BabelDOC text extraction failed, using MinerU fallback: %s",
                        error,
                    )
                    return await _run_mineru_scan_fallback(
                        translate_settings,
                        file_path,
                        lang_from,
                        lang_to,
                        progress,
                        "babeldoc_no_paragraphs",
                    )
                raise

        if file_path.suffix.lower() == ".pdf":
            _record_babeldoc_history(
                file_path,
                mono_path,
                dual_path,
                glossary_path,
                lang_from,
                lang_to,
            )
        if not mono_path or not mono_path.exists():
            mono_path = None
        else:
            mono_path = mono_path.as_posix()
        if not dual_path or not dual_path.exists():
            dual_path = None
        else:
            dual_path = dual_path.as_posix()

        if not glossary_path or not glossary_path.exists():
            glossary_path = None
        else:
            glossary_path = glossary_path.as_posix()
        # Build success UI updates
        return (
            str(mono_path) if mono_path else None,  # Output mono file
            str(mono_path) if mono_path else dual_path,  # PDF Preview
            None,  # HTML Preview (PDF不使用HTML预览)
            str(dual_path) if dual_path else None,  # Output dual file
            str(glossary_path) if glossary_path else None,  # Glossary file
            gr.update(visible=bool(mono_path)),  # Show mono download if available
            gr.update(visible=bool(dual_path)),  # Show dual download if available
            gr.update(
                visible=bool(glossary_path)
            ),  # Show glossary download if available
            gr.update(
                visible=bool(mono_path or dual_path)
            ),  # Show output title if any output
            gr.update(visible=True),  # Show PDF preview
            gr.update(visible=False),  # Hide HTML preview
        )
    except asyncio.CancelledError:
        gr.Info("Translation cancelled")
        # Return None for all outputs if cancelled
        return (
            None,  # Output mono file
            None,  # PDF Preview
            None,  # HTML Preview
            None,  # Output dual file
            None,  # Glossary file
            gr.update(visible=False),  # Hide mono download
            gr.update(visible=False),  # Hide dual download
            gr.update(visible=False),  # Hide glossary download
            gr.update(visible=False),  # Hide output title
            gr.update(visible=True),  # Show PDF preview (default)
            gr.update(visible=False),  # Hide HTML preview
        )
    except gr.Error:
        # Re-raise Gradio errors without modification
        raise
    except Exception as e:
        # Catch any other errors and wrap in gr.Error
        logger.exception(f"Error in translate_file: {e}")
        raise gr.Error(f"Translation failed: {e}") from e
    finally:
        # Clear task reference
        state["current_task"] = None


# Custom theme definition
custom_blue = gr.themes.Color(
    c50="#E8F3FF",
    c100="#BEDAFF",
    c200="#94BFFF",
    c300="#6AA1FF",
    c400="#4080FF",
    c500="#165DFF",  # Primary color
    c600="#0E42D2",
    c700="#0A2BA6",
    c800="#061D79",
    c900="#03114D",
    c950="#020B33",
)

custom_css = """
    .secondary-text {color: #999 !important;}
    footer {visibility: hidden}
    .env-warning {color: #dd5500 !important;}
    .env-success {color: #559900 !important;}

    /* Add dashed border to input-file class */
    .input-file {
        border: 1.2px dashed #165DFF !important;
        border-radius: 6px !important;
    }

    .progress-bar-wrap {
        border-radius: 8px !important;
    }

    .progress-bar {
        border-radius: 8px !important;
    }

    .pdf-canvas canvas {
        width: 100%;
    }
    
    /* Override system fonts to avoid 404 errors */
    * {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    }
    
    /* Prevent unnecessary font loading */
    @font-face {
        font-family: 'ui-sans-serif';
        src: local('Arial'), local('Helvetica');
    }
    
    @font-face {
        font-family: 'system-ui';
        src: local('Arial'), local('Helvetica');
    }
    """

# Build path to logo image
current_dir = Path(__file__).parent
project_root_dir = current_dir.parent
assets_dir = current_dir / "assets"
logo_path = assets_dir / "powered_by_siliconflow_light.png"
packaged_app_logo_path = assets_dir / "always-pi-logo.png"
legacy_app_logo_path = project_root_dir / "Logo 3D 渲染 (2)(1).png"
app_logo_path = (
    packaged_app_logo_path if packaged_app_logo_path.exists() else legacy_app_logo_path
)
app_logo_src = (
    f"/gradio_api/file={quote(app_logo_path.resolve().as_posix(), safe=':/')}"
    if app_logo_path.exists()
    else ""
)
app_logo_html = (
    f'<img class="app-hero-logo" src="{app_logo_src}" alt="Always Pi AI Studio Logo">'
    if app_logo_src
    else ""
)
ALLOWED_GUI_PATHS = [
    path for path in [logo_path, app_logo_path, OUTPUT_ROOT.resolve()] if path.exists()
]

tech_details_string = f"""
                    <summary>Technical details</summary>
                    - ⭐ Star at GitHub: <a href="https://github.com/PDFMathTranslate/PDFMathTranslate-next">PDFMathTranslate/PDFMathTranslate-next</a><br>
                    - BabelDOC: <a href="https://github.com/funstory-ai/BabelDOC">funstory-ai/BabelDOC</a><br>
                    - GUI by: <a href="https://github.com/reycn">Rongxin</a> & <a href="https://github.com/hellofinch">hellofinch</a> & <a href="https://github.com/awwaawwa">awwaawwa</a><br>
                    - pdf2zh Version: {__version__} <br>
                    - BabelDOC Version: {babeldoc_version}<br>
                    - Free translation service provided by <a href="https://siliconflow.cn/" target="_blank" style="text-decoration: none;">SiliconFlow</a><br>
                    <a href="https://siliconflow.cn/" target="_blank" style="text-decoration: none;">
                        <img src="/gradio_api/file={logo_path}" alt="Powered By SiliconFlow" style="height: 40px; margin-top: 10px;">
                    </a>
                    <br>
                """

_sync_legacy_history_to_output()

app_header_html = f"""
<section class="app-hero">
    <div class="app-hero-copy">
        <div class="app-hero-kicker">Always <span class="brand-pi">π</span> AI Studio</div>
        <h1>PDF文件翻译工具</h1>
        <p>普通PDF保留版式；扫描件先识别结构，再生成 Markdown、HTML 和标准 PDF。</p>
        <div class="app-hero-pills">
            <span>BabelDOC</span>
            <span>MinerU</span>
            <span>历史文件</span>
        </div>
    </div>
    <div class="app-hero-art">{app_logo_html}</div>
</section>
"""


def pdf_preview_toolbar_html(target_id: str) -> str:
    return f"""
    <div class="pdf-preview-toolbar" data-pdf-preview-toolbar="{target_id}">
        <div class="pdf-preview-toolbar-title">PDF预览</div>
        <div class="pdf-preview-actions">
            <button type="button" title="缩小" aria-label="缩小PDF预览" onclick="return window.pdf2zhPdfViewerAction && window.pdf2zhPdfViewerAction('{target_id}', 'out')">−</button>
            <span class="pdf-preview-zoom-value" data-pdf2zh-zoom-indicator="{target_id}">100%</span>
            <button type="button" title="放大" aria-label="放大PDF预览" onclick="return window.pdf2zhPdfViewerAction && window.pdf2zhPdfViewerAction('{target_id}', 'in')">＋</button>
            <button type="button" title="适应宽度" aria-label="适应宽度" onclick="return window.pdf2zhPdfViewerAction && window.pdf2zhPdfViewerAction('{target_id}', 'fit')">适宽</button>
        </div>
    </div>
    """


PDF_PREVIEW_RENDER_HEIGHT = 3200


# The following code creates the GUI
with gr.Blocks(
    title="PDF文件翻译工具",
    theme=create_custom_theme(),
    css=get_custom_css(),
    head=get_vanta_js(),
) as demo:
    gr.HTML(app_header_html)
    ui_language = gr.Radio(
        choices=UI_LANGUAGE_CHOICES,
        label="界面语言 / UI Language",
        value=UI_LANGUAGE_DEFAULT,
        interactive=True,
    )

    translation_engine_arg_inputs = []
    detail_text_inputs = []
    require_llm_translator_inputs = []
    detail_text_input_index_map = {}
    LLM_support_index_map = {}
    __gui_service_arg_descriptions = []
    state = gr.State({"session_id": None, "current_task": None})

    # 创建Tabs结构
    with gr.Tabs(elem_id="main_tabs") as main_tabs:
        # ==================== Tab 1: PDF Translation (BabelDOC) ====================
        with gr.Tab("📄 PDF翻译 (BabelDOC)", id="pdf_translation"):
            babeldoc_title = gr.Markdown("## PDF翻译 (BabelDOC)")

            with gr.Row():
                with gr.Column(scale=1):
                    # ========== 文件上传区域 ==========
                    with gr.Group():
                        babeldoc_upload_heading = gr.Markdown("### 📁 文件上传")
                        file_type = gr.Radio(
                            choices=file_type_choices(),
                            label="输入类型",
                            value="File",
                        )
                        file_input = gr.File(
                            label="文件",
                            file_count="single",
                            file_types=[".pdf", ".PDF", ".md", ".markdown"],
                            type="filepath",
                            elem_classes=["input-file"],
                        )
                        link_input = gr.Textbox(
                            label="链接",
                            visible=False,
                            interactive=True,
                        )

                    # ========== 翻译引擎设置 ==========
                    with gr.Group():
                        babeldoc_engine_heading = gr.Markdown("### 🔧 翻译引擎")

                        siliconflow_free_acknowledgement = gr.Markdown(
                            "免费翻译服务由 [SiliconFlow](https://siliconflow.cn) 提供",
                            visible=selected_translation_service == "SiliconFlowFree",
                        )

                        detail_index = 0
                        service = gr.Dropdown(
                            label="翻译引擎",
                            choices=available_services,
                            value=selected_translation_service,
                        )

                        __gui_service_arg_names = []
                        __gui_service_arg_service_names = []
                        for service_name in available_services:
                            metadata = TRANSLATION_ENGINE_METADATA_MAP[service_name]
                            LLM_support_index_map[metadata.translate_engine_type] = (
                                metadata.support_llm
                            )
                            if not metadata.cli_detail_field_name:
                                # no detail field, no need to show
                                continue
                            detail_settings = getattr(
                                settings, metadata.cli_detail_field_name
                            )
                            visible = service.value == metadata.translate_engine_type

                            # OpenAI specific settings (initially visible if OpenAI is default)
                            with gr.Group(visible=True) as service_detail:
                                detail_text_input_index_map[
                                    metadata.translate_engine_type
                                ] = []
                                for (
                                    field_name,
                                    field,
                                ) in metadata.setting_model_type.model_fields.items():
                                    if disable_gui_sensitive_input:
                                        if field_name in GUI_SENSITIVE_FIELDS:
                                            continue
                                        if field_name in GUI_PASSWORD_FIELDS:
                                            continue
                                    if field.default_factory:
                                        continue

                                    if field_name == "translate_engine_type":
                                        continue
                                    if field_name == "support_llm":
                                        continue
                                    type_hint = field.annotation
                                    original_type = typing.get_origin(type_hint)
                                    type_args = typing.get_args(type_hint)
                                    value = getattr(detail_settings, field_name)
                                    if (
                                        type_hint is str
                                        or str in type_args
                                        or type_hint is int
                                        or int in type_args
                                    ):
                                        if field_name in GUI_PASSWORD_FIELDS:
                                            field_input = gr.Textbox(
                                                label=engine_field_label(
                                                    field_name, field.description
                                                ),
                                                value=value,
                                                interactive=True,
                                                type="password",
                                                visible=visible,
                                            )
                                        else:
                                            field_input = gr.Textbox(
                                                label=engine_field_label(
                                                    field_name, field.description
                                                ),
                                                value=value,
                                                interactive=True,
                                                visible=visible,
                                            )
                                    elif type_hint is bool or bool in type_args:
                                        field_input = gr.Checkbox(
                                            label=engine_field_label(
                                                field_name, field.description
                                            ),
                                            value=value,
                                            interactive=True,
                                            visible=visible,
                                        )
                                    else:
                                        raise Exception(
                                            f"Unsupported type {type_hint} for field {field_name} in gui translation engine settings"
                                        )
                                    detail_text_input_index_map[
                                        metadata.translate_engine_type
                                    ].append(detail_index)
                                    detail_index += 1
                                    detail_text_inputs.append(field_input)
                                    __gui_service_arg_names.append(field_name)
                                    __gui_service_arg_service_names.append(
                                        metadata.translate_engine_type
                                    )
                                    translation_engine_arg_inputs.append(field_input)
                                    __gui_service_arg_descriptions.append(
                                        field.description or field_name
                                    )

                        with gr.Row():
                            babeldoc_engine_save_btn = gr.Button(
                                "保存设置", variant="primary", size="sm"
                            )
                            babeldoc_engine_test_btn = gr.Button("测试连接", size="sm")
                        babeldoc_engine_status = gr.Markdown(value="", visible=False)

                    # ========== 基础翻译选项 ==========
                    with gr.Group():
                        babeldoc_translation_heading = gr.Markdown("### 🌐 翻译设置")
                        with gr.Row():
                            lang_from = gr.Dropdown(
                                label="源语言",
                                choices=list(lang_map.keys()),
                                value=default_lang_from,
                                interactive=True,
                            )
                            lang_to = gr.Dropdown(
                                label="目标语言",
                                choices=list(lang_map.keys()),
                                value=default_lang_to,
                                interactive=True,
                            )

                        page_range = gr.Radio(
                            choices=page_range_choices(),
                            label="页码范围",
                            value="All",
                            interactive=True,
                        )

                        page_input = gr.Textbox(
                            label="自定义页码范围（如 1,3,5-10,-5）",
                            visible=False,
                            interactive=True,
                            placeholder="例如：1,3,5-10",
                        )

                        only_include_translated_page = gr.Checkbox(
                            label="输出 PDF 只包含已翻译页",
                            info="仅在指定页码范围时生效。",
                            value=settings.pdf.only_include_translated_page,
                            interactive=True,
                        )

                    # ========== 速率限制设置 (Accordion) ==========
                    with gr.Accordion("⚡ 速率限制设置 / Rate limits", open=False):
                        rate_limit_mode = gr.Radio(
                            choices=rate_limit_mode_choices(),
                            label="速率限制模式",
                            value="Custom",
                            interactive=True,
                            visible=False,
                            info="选择 API 供应商对应的限速方式，点击翻译时会自动换算为 QPS 和线程数。",
                        )

                        rpm_input = gr.Number(
                            label="RPM（每分钟请求数）",
                            value=240,  # More conservative default value
                            precision=0,
                            minimum=1,
                            maximum=10000,
                            interactive=True,
                            visible=False,
                            info="多数 API 服务商会提供该参数，例如 OpenAI GPT-4: 500 RPM。",
                        )

                        concurrent_threads_input = gr.Number(
                            label="并发线程数",
                            value=20,  # More conservative default value
                            precision=0,
                            minimum=1,
                            maximum=200,
                            interactive=True,
                            visible=False,
                            info="同时处理请求的最大数量。",
                        )

                        custom_qps_input = gr.Number(
                            label="QPS（每秒请求数）",
                            value=settings.translation.qps or 4,
                            precision=0,
                            minimum=1,
                            maximum=100,
                            interactive=True,
                            visible=False,
                            info="每秒发送的请求数量。",
                        )

                        custom_pool_max_workers_input = gr.Number(
                            label="最大工作线程数",
                            value=settings.translation.pool_max_workers,
                            precision=0,
                            minimum=0,
                            maximum=1000,
                            interactive=True,
                            visible=False,
                            info="不填或为 0 时，会使用 QPS 作为线程数。",
                        )

                    # ========== PDF输出选项 (Accordion) ==========
                    with gr.Accordion("📄 PDF输出选项 / PDF output", open=False):
                        with gr.Row():
                            no_mono = gr.Checkbox(
                                label="禁用单语输出",
                                value=settings.pdf.no_mono,
                                interactive=True,
                            )
                            no_dual = gr.Checkbox(
                                label="禁用双语输出",
                                value=settings.pdf.no_dual,
                                interactive=True,
                            )

                        with gr.Row():
                            dual_translate_first = gr.Checkbox(
                                label="双语 PDF 中译文页在前",
                                value=settings.pdf.dual_translate_first,
                                interactive=True,
                            )
                            use_alternating_pages_dual = gr.Checkbox(
                                label="双语 PDF 使用原文/译文交替页",
                                value=settings.pdf.use_alternating_pages_dual,
                                interactive=True,
                            )

                        watermark_output_mode = gr.Radio(
                            choices=watermark_mode_choices(),
                            label="水印模式",
                            value="Watermarked"
                            if settings.pdf.watermark_output_mode.value == "watermarked"
                            else "No Watermark",
                        )

                    # ========== 高级翻译选项 (Accordion) ==========
                    with gr.Accordion(
                        "🔬 高级翻译选项 / Advanced translation", open=False
                    ):
                        prompt = gr.Textbox(
                            label="自定义翻译提示词",
                            value="",
                            visible=False,
                            interactive=True,
                            placeholder="给翻译模型的自定义提示词",
                        )

                        # New Textbox for custom_system_prompt
                        custom_system_prompt_input = gr.Textbox(
                            label="自定义系统提示词",
                            value=settings.translation.custom_system_prompt or "",
                            interactive=True,
                            placeholder="例如：/no_think You are a professional, authentic machine translation engine.",
                        )

                        min_text_length = gr.Number(
                            label="最小翻译文本长度",
                            value=settings.translation.min_text_length,
                            precision=0,
                            minimum=0,
                            interactive=True,
                        )

                        rpc_doclayout = gr.Textbox(
                            label="文档布局分析 RPC 服务（可选）",
                            value=settings.translation.rpc_doclayout or "",
                            visible=False,
                            interactive=True,
                            placeholder="http://host:port",
                        )

                        # New advanced translation options
                        no_auto_extract_glossary = gr.Checkbox(
                            label="禁用自动术语提取",
                            value=settings.translation.no_auto_extract_glossary,
                            interactive=True,
                        )

                        save_auto_extracted_glossary = gr.Checkbox(
                            label="保存自动提取的术语表",
                            value=settings.translation.save_auto_extracted_glossary,
                            interactive=True,
                        )

                        primary_font_family = gr.Dropdown(
                            label="译文主字体族",
                            choices=["Auto", "serif", "sans-serif", "script"],
                            value="Auto"
                            if not settings.translation.primary_font_family
                            else settings.translation.primary_font_family,
                            interactive=True,
                        )

                        glossary_file = gr.File(
                            label="术语表文件",
                            file_count="multiple",
                            file_types=[".csv"],
                            type="binary",
                            visible=True,
                        )
                        require_llm_translator_inputs.append(glossary_file)

                        glossary_table = gr.Dataframe(
                            headers=["source", "target"],
                            datatype=["str", "str"],
                            interactive=False,
                            col_count=(2, "fixed"),
                            visible=False,
                        )
                        require_llm_translator_inputs.append(glossary_table)

                        # PDF options section
                        pdf_advanced_heading = gr.Markdown("#### PDF高级选项")

                        skip_clean = gr.Checkbox(
                            label="跳过清理（可能提升兼容性）",
                            value=settings.pdf.skip_clean,
                            interactive=True,
                        )

                        disable_rich_text_translate = gr.Checkbox(
                            label="禁用富文本翻译（可能提升兼容性）",
                            value=settings.pdf.disable_rich_text_translate,
                            interactive=True,
                        )

                        enhance_compatibility = gr.Checkbox(
                            label="增强兼容性（自动启用跳过清理和禁用富文本）",
                            value=settings.pdf.enhance_compatibility,
                            interactive=True,
                        )

                        split_short_lines = gr.Checkbox(
                            label="强制将短行拆成不同段落",
                            value=settings.pdf.split_short_lines,
                            interactive=True,
                        )

                        short_line_split_factor = gr.Slider(
                            label="短行拆分阈值系数",
                            value=settings.pdf.short_line_split_factor,
                            minimum=0.1,
                            maximum=1.0,
                            step=0.1,
                            interactive=True,
                            visible=settings.pdf.split_short_lines,
                        )

                        translate_table_text = gr.Checkbox(
                            label="翻译表格文本（实验）",
                            value=settings.pdf.translate_table_text,
                            interactive=True,
                        )

                        skip_scanned_detection = gr.Checkbox(
                            label="跳过扫描件检测",
                            value=settings.pdf.skip_scanned_detection,
                            interactive=True,
                        )

                        ocr_workaround = gr.Checkbox(
                            label="OCR 兼容模式（实验，会在后端自动启用跳过扫描件检测）",
                            value=settings.pdf.ocr_workaround,
                            interactive=True,
                        )

                        auto_enable_ocr_workaround = gr.Checkbox(
                            label="自动启用 OCR 兼容模式（适合重度扫描文档）",
                            value=settings.pdf.auto_enable_ocr_workaround,
                            interactive=True,
                        )

                        max_pages_per_part = gr.Number(
                            label="每个分片最大页数（自动拆分翻译，0 表示不限）",
                            value=settings.pdf.max_pages_per_part,
                            precision=0,
                            minimum=0,
                            interactive=True,
                        )

                        formular_font_pattern = gr.Textbox(
                            label="公式文本字体识别规则（正则，不建议修改）",
                            value=settings.pdf.formular_font_pattern or "",
                            interactive=True,
                            placeholder="e.g., CMMI|CMR",
                        )

                        formular_char_pattern = gr.Textbox(
                            label="公式文本字符识别规则（正则，不建议修改）",
                            value=settings.pdf.formular_char_pattern or "",
                            interactive=True,
                            placeholder="e.g., [∫∬∭∮∯∰∇∆]",
                        )

                        ignore_cache = gr.Checkbox(
                            label="忽略缓存",
                            value=settings.translation.ignore_cache,
                            interactive=True,
                        )

                        # BabelDOC v0.5.1 new options
                        babeldoc_advanced_heading = gr.Markdown("#### BabelDOC高级选项")

                        merge_alternating_line_numbers = gr.Checkbox(
                            label="合并交替行号",
                            info="处理带行号文档中的交替行号和正文段落。",
                            value=not settings.pdf.no_merge_alternating_line_numbers,
                            interactive=True,
                        )

                        remove_non_formula_lines = gr.Checkbox(
                            label="移除非公式行",
                            info="移除段落区域内的非公式行。",
                            value=not settings.pdf.no_remove_non_formula_lines,
                            interactive=True,
                        )

                        non_formula_line_iou_threshold = gr.Slider(
                            label="非公式行 IoU 阈值",
                            info="用于识别非公式行的 IoU 阈值。",
                            value=settings.pdf.non_formula_line_iou_threshold,
                            minimum=0.0,
                            maximum=1.0,
                            step=0.05,
                            interactive=True,
                        )

                        figure_table_protection_threshold = gr.Slider(
                            label="图表保护阈值",
                            info="图表区域保护阈值，图表内的线条不会被处理。",
                            value=settings.pdf.figure_table_protection_threshold,
                            minimum=0.0,
                            maximum=1.0,
                            step=0.05,
                            interactive=True,
                        )

                        skip_formula_offset_calculation = gr.Checkbox(
                            label="跳过公式偏移计算",
                            info="处理过程中跳过公式偏移计算。",
                            value=settings.pdf.skip_formula_offset_calculation,
                            interactive=True,
                        )

                    # ========== 操作按钮 ==========
                    with gr.Row():
                        translate_btn = gr.Button(
                            "🚀 开始翻译", variant="primary", size="lg"
                        )
                        cancel_btn = gr.Button("⏹️ 取消", variant="secondary", size="lg")

                    # ========== 输出文件 ==========
                    output_title = gr.Markdown("## 📥 翻译结果", visible=False)
                    output_file_mono = gr.File(label="下载译文 (单语)", visible=False)
                    output_file_dual = gr.File(label="下载译文 (双语)", visible=False)
                    output_file_glossary = gr.File(
                        label="下载自动提取的术语表", visible=False
                    )

                    # ========== 技术信息 ==========
                    tech_details = gr.Markdown(
                        tech_details_string,
                        elem_classes=["secondary-text"],
                    )

            with gr.Column(scale=2):
                babeldoc_preview_heading = gr.Markdown("## 预览")
                gr.HTML(pdf_preview_toolbar_html("babeldoc_pdf_preview"))
                preview = PDF(
                    label="PDF预览",
                    visible=True,
                    height=PDF_PREVIEW_RENDER_HEIGHT,
                    elem_id="babeldoc_pdf_preview",
                    elem_classes=["pdf-viewer-zoomable"],
                )
                html_preview = gr.HTML(label="Markdown 预览", visible=False)
                babeldoc_history_heading = gr.Markdown("## 历史记录")
                pdf_history_initial_rows = refresh_babeldoc_history()
                pdf_history_state = gr.State(pdf_history_initial_rows)
                pdf_history_preview_choice = gr.Radio(
                    label="点击文件预览",
                    choices=_history_choice_labels(pdf_history_initial_rows),
                    value=None,
                    interactive=True,
                    elem_classes=["history-card-picker"],
                )
                pdf_history_download_choice = gr.Dropdown(
                    label="下载历史文件",
                    choices=_history_choice_labels(pdf_history_initial_rows),
                    value=None,
                    interactive=True,
                    elem_classes=["history-picker"],
                )
                with gr.Row():
                    pdf_history_refresh_btn = gr.Button("刷新历史记录", size="sm")
                    pdf_history_delete_btn = gr.Button(
                        "删除选中文件", variant="stop", size="sm"
                    )
                    pdf_history_download = gr.DownloadButton(
                        "下载历史文件", visible=False
                    )
                pdf_history_delete_status = gr.Markdown(value="", visible=False)

        # Event handlers
        def on_select_filetype(file_type):
            """Update visibility based on selected file type"""
            return (
                gr.update(visible=file_type == "File"),
                gr.update(visible=file_type == "Link"),
            )

        def on_select_page(choice):
            """Update page input visibility based on selection"""
            return gr.update(visible=choice == "Range")

        def on_select_service(service_name):
            """Update service-specific settings visibility"""
            if not detail_text_inputs:
                return
            detail_group_index = detail_text_input_index_map.get(service_name, [])
            llm_support = LLM_support_index_map.get(service_name, False)
            siliconflow_free_acknowledgement_visible = service_name == "SiliconFlowFree"
            siliconflow_update = [
                gr.update(visible=siliconflow_free_acknowledgement_visible)
            ]
            return_list = []
            glossary_updates = [
                gr.update(visible=llm_support)
                for i in range(len(require_llm_translator_inputs))
            ]
            if len(detail_text_inputs) == 1:
                return_list = (
                    siliconflow_update
                    + glossary_updates
                    + [gr.update(visible=(0 in detail_group_index))]
                )
            else:
                return_list = (
                    siliconflow_update
                    + glossary_updates
                    + [
                        gr.update(visible=(i in detail_group_index))
                        for i in range(len(detail_text_inputs))
                    ]
                )
            return return_list

        def on_enhance_compatibility_change(enhance_value):
            """Update skip_clean and disable_rich_text_translate when enhance_compatibility changes"""
            if enhance_value:
                # When enhanced compatibility is enabled, both options are auto-enabled and disabled for user modification
                return (
                    gr.update(value=True, interactive=False),
                    gr.update(value=True, interactive=False),
                )
            else:
                # When disabled, allow user to modify these settings
                return (
                    gr.update(interactive=True),
                    gr.update(interactive=True),
                )

        def on_split_short_lines_change(split_value):
            """Update short_line_split_factor visibility based on split_short_lines value"""
            return gr.update(visible=split_value)

        def on_glossary_file_change(glossary_file):
            if glossary_file is None:
                return gr.update(visible=False)

            glossary_list = []
            for file in glossary_file:
                file_encoding = chardet.detect(file)["encoding"]
                content = file.decode(file_encoding).replace("\r\n", "\n").strip()
                with io.StringIO(content) as f:
                    csvreader = csv.reader(f, delimiter=",", doublequote=True)
                    next(csvreader)  # Skip header
                    for line in csvreader:
                        if line:
                            glossary_list.append(line)
            logger.warning(f"on_glossary_file_delete glossary_list {glossary_list}")
            if not glossary_list:
                glossary_list = ["", "", ""]
            return gr.update(visible=True, value=glossary_list)

        def on_rate_limit_mode_change(mode, service_name):
            """Update rate-limit-specific-settings visibility based on rate_limit_mode value"""
            if service_name == "SiliconFlowFree":
                return [gr.update(visible=False)] * 4  # Hide all options

            rpm_visible = mode == "RPM"
            threads_visible = mode == "Concurrent Threads"
            custom_visible = mode == "Custom"

            return [
                gr.update(visible=rpm_visible),
                gr.update(visible=threads_visible),
                gr.update(visible=custom_visible),
                gr.update(visible=custom_visible),
            ]

        def on_service_change_with_rate_limit(mode, service_name):
            """Expand original on_select_service with rate-limit-UI updated"""
            original_updates = on_select_service(service_name)

            rate_limit_visible = service_name != "SiliconFlowFree"

            detailed_visible = [gr.update(visible=False)] * 4

            if rate_limit_visible:
                detailed_visible = on_rate_limit_mode_change(mode, service_name)

            # Add updates of rate-limit-UI
            rate_limit_updates = [
                gr.update(visible=rate_limit_visible),
            ]

            return original_updates + rate_limit_updates + detailed_visible

        def save_babeldoc_translation_engine_defaults(service_name, *detail_values):
            _persist_translation_engine_gui_defaults(
                service_name,
                __gui_service_arg_names,
                __gui_service_arg_service_names,
                detail_values,
            )

        def save_babeldoc_translation_engine_defaults_with_status(
            service_name, *detail_values
        ):
            ok, message = _persist_translation_engine_gui_defaults(
                service_name,
                __gui_service_arg_names,
                __gui_service_arg_service_names,
                detail_values,
            )
            return _translation_engine_status_update(ok, message)

        def test_babeldoc_translation_engine_connection(service_name, *detail_values):
            ok, message = _test_translation_engine_connection(
                service_name,
                __gui_service_arg_names,
                __gui_service_arg_service_names,
                detail_values,
            )
            return _translation_engine_status_update(ok, message)

        def load_babeldoc_translation_engine_defaults():
            return _load_translation_engine_gui_updates(
                __gui_service_arg_names,
                __gui_service_arg_service_names,
            )

        # File upload handler
        def handle_file_upload(file_path):
            """处理文件上传，根据文件类型显示不同预览"""
            if not file_path:
                return None, gr.update(visible=False), gr.update(visible=False)

            file_ext = Path(file_path).suffix.lower()

            if file_ext in [".md", ".markdown"]:
                # Markdown文件：显示文本预览
                try:
                    content = Path(file_path).read_text(encoding="utf-8")
                    # 生成简单的HTML预览
                    preview_html = f"""
                    <div style="padding: 20px; font-family: Arial, sans-serif; line-height: 1.6;">
                        <h3>📄 Markdown文件预览</h3>
                        <div style="background: #f8f9fa; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff;">
                            <strong>文件名:</strong> {Path(file_path).name}<br>
                            <strong>大小:</strong> {len(content)} 字符<br>
                            <strong>行数:</strong> {len(content.split(chr(10)))} 行
                        </div>
                        <h4>内容预览:</h4>
                        <pre style="background: #f8f9fa; padding: 15px; border-radius: 5px; overflow: auto; max-height: 400px; white-space: pre-wrap;">{content}</pre>
                    </div>
                    """
                    return (
                        None,  # PDF预览为空
                        gr.update(visible=False),  # 隐藏PDF预览
                        gr.update(value=preview_html, visible=True),  # 显示HTML预览
                    )
                except Exception as e:
                    error_html = f"""
                    <div style="padding: 20px; color: red;">
                        <h3>❌ 文件读取失败</h3>
                        <p>错误信息: {str(e)}</p>
                    </div>
                    """
                    return (
                        None,
                        gr.update(visible=False),
                        gr.update(value=error_html, visible=True),
                    )
            else:
                # PDF文件：显示PDF预览
                return (
                    file_path,  # PDF预览
                    gr.update(visible=True),  # 显示PDF预览
                    gr.update(visible=False),  # 隐藏HTML预览
                )

        file_input.upload(
            handle_file_upload,
            inputs=file_input,
            outputs=[preview, preview, html_preview],
        )

        pdf_history_refresh_btn.click(
            refresh_babeldoc_history_picker,
            outputs=[
                pdf_history_preview_choice,
                pdf_history_download_choice,
                pdf_history_state,
                pdf_history_download,
            ],
        )

        pdf_history_preview_choice.change(
            preview_selected_history_file_only,
            inputs=[pdf_history_state, pdf_history_preview_choice],
            outputs=[preview, html_preview],
        )

        pdf_history_download_choice.change(
            selected_history_file_download,
            inputs=[pdf_history_state, pdf_history_download_choice],
            outputs=[pdf_history_download],
        )

        pdf_history_delete_btn.click(
            delete_selected_babeldoc_history_file,
            inputs=[pdf_history_state, pdf_history_preview_choice],
            outputs=[
                pdf_history_preview_choice,
                pdf_history_download_choice,
                pdf_history_state,
                pdf_history_download,
                preview,
                html_preview,
                pdf_history_delete_status,
            ],
        )

        # Event bindings
        file_type.select(
            on_select_filetype,
            file_type,
            [file_input, link_input],
        )

        page_range.select(
            on_select_page,
            page_range,
            page_input,
        )

        on_select_service_outputs = (
            [siliconflow_free_acknowledgement]
            + require_llm_translator_inputs
            + detail_text_inputs
        )

        service.change(
            on_service_change_with_rate_limit,
            [rate_limit_mode, service],
            outputs=(
                on_select_service_outputs
                if len(on_select_service_outputs) > 0
                else None
            )
            + [
                rate_limit_mode,
                rpm_input,
                concurrent_threads_input,
                custom_qps_input,
                custom_pool_max_workers_input,
            ],
        )

        service.change(
            save_babeldoc_translation_engine_defaults,
            inputs=[service] + detail_text_inputs,
        )

        for detail_input in detail_text_inputs:
            detail_input.change(
                save_babeldoc_translation_engine_defaults,
                inputs=[service] + detail_text_inputs,
            )

        babeldoc_engine_save_btn.click(
            save_babeldoc_translation_engine_defaults_with_status,
            inputs=[service] + detail_text_inputs,
            outputs=[babeldoc_engine_status],
        )

        babeldoc_engine_test_btn.click(
            test_babeldoc_translation_engine_connection,
            inputs=[service] + detail_text_inputs,
            outputs=[babeldoc_engine_status],
        )

        demo.load(
            load_babeldoc_translation_engine_defaults,
            outputs=[service, siliconflow_free_acknowledgement] + detail_text_inputs,
        )

        rate_limit_mode.change(
            on_rate_limit_mode_change,
            inputs=[rate_limit_mode, service],
            outputs=[
                rpm_input,
                concurrent_threads_input,
                custom_qps_input,
                custom_pool_max_workers_input,
            ],
        )

        glossary_file.change(
            on_glossary_file_change,
            glossary_file,
            outputs=glossary_table,
        )

        # Add event handler for enhance_compatibility
        enhance_compatibility.change(
            on_enhance_compatibility_change,
            enhance_compatibility,
            [skip_clean, disable_rich_text_translate],
        )

        # Add event handler for split_short_lines
        split_short_lines.change(
            on_split_short_lines_change,
            split_short_lines,
            short_line_split_factor,
        )

        # Translation button click handler
        translate_event = translate_btn.click(
            translate_file,
            inputs=[
                file_type,
                file_input,
                link_input,
                service,
                lang_from,
                lang_to,
                page_range,
                page_input,
                # PDF Output Options
                no_mono,
                no_dual,
                dual_translate_first,
                use_alternating_pages_dual,
                watermark_output_mode,
                # Rate Limit Options
                rate_limit_mode,
                rpm_input,
                concurrent_threads_input,
                custom_qps_input,
                custom_pool_max_workers_input,
                # Advanced Options
                prompt,
                min_text_length,
                rpc_doclayout,
                custom_system_prompt_input,
                glossary_file,
                save_auto_extracted_glossary,
                # New advanced translation options
                no_auto_extract_glossary,
                primary_font_family,
                skip_clean,
                disable_rich_text_translate,
                enhance_compatibility,
                split_short_lines,
                short_line_split_factor,
                translate_table_text,
                skip_scanned_detection,
                max_pages_per_part,
                formular_font_pattern,
                formular_char_pattern,
                ignore_cache,
                state,
                ocr_workaround,
                auto_enable_ocr_workaround,
                only_include_translated_page,
                # BabelDOC v0.5.1 new options
                merge_alternating_line_numbers,
                remove_non_formula_lines,
                non_formula_line_iou_threshold,
                figure_table_protection_threshold,
                skip_formula_offset_calculation,
                *translation_engine_arg_inputs,
            ],
            outputs=[
                output_file_mono,  # Mono file
                preview,  # PDF Preview
                html_preview,  # HTML Preview
                output_file_dual,  # Dual file
                output_file_glossary,  # Glossary file
                output_file_mono,  # Visibility of mono output
                output_file_dual,  # Visibility of dual output
                output_file_glossary,  # Visibility of glossary output
                output_title,  # Visibility of output title
                preview,  # Visibility of PDF preview
                html_preview,  # Visibility of HTML preview
            ],
        )

        translate_event.then(
            refresh_babeldoc_history_picker,
            outputs=[
                pdf_history_preview_choice,
                pdf_history_download_choice,
                pdf_history_state,
                pdf_history_download,
            ],
        )

        # Cancel button click handler
        cancel_btn.click(
            stop_translate_file,
            inputs=[state],
        )

        # ==================== Tab 2: MinerU Translation ====================
        with gr.Tab("📄 扫描PDF翻译 (MinerU)", id="mineru_translation"):
            mineru_title = gr.Markdown("## 扫描PDF翻译 (MinerU)")

            with gr.Row():
                with gr.Column(scale=1):
                    # ========== 文件上传 ==========
                    with gr.Group():
                        mineru_upload_heading = gr.Markdown("### 📁 文件上传")
                        mineru_file = gr.File(
                            label="上传PDF文件",
                            file_types=[".pdf", ".PDF"],
                            type="filepath",
                            elem_classes=["input-file"],
                        )

                    # ========== 翻译引擎设置 ==========
                    with gr.Group():
                        mineru_engine_heading = gr.Markdown("### 🔧 翻译引擎")

                        mineru_siliconflow_free_acknowledgement = gr.Markdown(
                            "免费翻译服务由 [SiliconFlow](https://siliconflow.cn) 提供",
                            visible=selected_translation_service == "SiliconFlowFree",
                        )

                        mineru_service = gr.Dropdown(
                            label="翻译引擎",
                            choices=available_services,
                            value=selected_translation_service,
                        )

                        # 为MinerU Tab创建独立的翻译引擎详细设置
                        mineru_detail_text_inputs = []
                        mineru_translation_engine_arg_inputs = []
                        mineru_translation_engine_arg_names = []
                        mineru_translation_engine_arg_descriptions = []
                        mineru_translation_engine_arg_service_names = []
                        mineru_detail_text_input_index_map = {}
                        mineru_detail_index = 0

                        for service_name in available_services:
                            metadata = TRANSLATION_ENGINE_METADATA_MAP[service_name]
                            if not metadata.cli_detail_field_name:
                                continue
                            detail_settings = getattr(
                                settings, metadata.cli_detail_field_name
                            )
                            visible = (
                                mineru_service.value == metadata.translate_engine_type
                            )

                            with gr.Group(visible=True):
                                mineru_detail_text_input_index_map[
                                    metadata.translate_engine_type
                                ] = []
                                for (
                                    field_name,
                                    field,
                                ) in metadata.setting_model_type.model_fields.items():
                                    if disable_gui_sensitive_input:
                                        if (
                                            field_name in GUI_SENSITIVE_FIELDS
                                            or field_name in GUI_PASSWORD_FIELDS
                                        ):
                                            continue
                                    if field.default_factory:
                                        continue
                                    if field_name in [
                                        "translate_engine_type",
                                        "support_llm",
                                    ]:
                                        continue

                                    type_hint = field.annotation
                                    type_args = typing.get_args(type_hint)
                                    value = getattr(detail_settings, field_name)

                                    if (
                                        type_hint is str
                                        or str in type_args
                                        or type_hint is int
                                        or int in type_args
                                    ):
                                        if field_name in GUI_PASSWORD_FIELDS:
                                            field_input = gr.Textbox(
                                                label=engine_field_label(
                                                    field_name, field.description
                                                ),
                                                value=value,
                                                interactive=True,
                                                type="password",
                                                visible=visible,
                                            )
                                        else:
                                            field_input = gr.Textbox(
                                                label=engine_field_label(
                                                    field_name, field.description
                                                ),
                                                value=value,
                                                interactive=True,
                                                visible=visible,
                                            )
                                    elif type_hint is bool or bool in type_args:
                                        field_input = gr.Checkbox(
                                            label=engine_field_label(
                                                field_name, field.description
                                            ),
                                            value=value,
                                            interactive=True,
                                            visible=visible,
                                        )
                                    else:
                                        continue

                                    mineru_detail_text_input_index_map[
                                        metadata.translate_engine_type
                                    ].append(mineru_detail_index)
                                    mineru_detail_index += 1
                                    mineru_detail_text_inputs.append(field_input)
                                    mineru_translation_engine_arg_inputs.append(
                                        field_input
                                    )
                                    mineru_translation_engine_arg_names.append(
                                        field_name
                                    )
                                    mineru_translation_engine_arg_descriptions.append(
                                        field.description or field_name
                                    )
                                    mineru_translation_engine_arg_service_names.append(
                                        metadata.translate_engine_type
                                    )

                        with gr.Row():
                            mineru_engine_save_btn = gr.Button(
                                "保存设置", variant="primary", size="sm"
                            )
                            mineru_engine_test_btn = gr.Button("测试连接", size="sm")
                        mineru_engine_status = gr.Markdown(value="", visible=False)

                    # ========== 基础翻译选项 ==========
                    with gr.Group():
                        mineru_translation_heading = gr.Markdown("### 🌐 翻译设置")
                        with gr.Row():
                            mineru_lang_from = gr.Dropdown(
                                label="源语言",
                                choices=list(lang_map.keys()),
                                value=default_lang_from,
                                interactive=True,
                            )
                            mineru_lang_to = gr.Dropdown(
                                label="目标语言",
                                choices=list(lang_map.keys()),
                                value=default_lang_to,
                                interactive=True,
                            )

                        mineru_output_format = gr.Radio(
                            choices=mineru_output_format_choices(),
                            label="输出格式",
                            value="Markdown",
                            info="选择翻译结果的输出格式",
                            interactive=True,
                        )

                    # ========== MinerU特定选项 ==========
                    with gr.Accordion("🦅 MinerU设置 / MinerU settings", open=False):
                        mineru_model_path = gr.Textbox(
                            label="模型路径",
                            value=settings.mineru.model_path,
                            info="仅本地/vLLM后端使用：HuggingFace模型ID或本地路径",
                            interactive=True,
                            visible=mineru_default_backend
                            not in MINERU_ONLINE_BACKENDS,
                        )
                        mineru_backend = gr.Radio(
                            choices=MINERU_BACKEND_CHOICES,
                            label="后端",
                            value=mineru_default_backend,
                            info="online-api: 官方精准解析 | online-agent: 官方轻量解析 | http-client: 本地vLLM",
                        )
                        mineru_local_backend_hint = gr.Markdown(
                            MINERU_LOCAL_SETUP_HINT,
                            visible=mineru_default_backend
                            not in MINERU_ONLINE_BACKENDS,
                            elem_classes=["secondary-text"],
                        )
                        mineru_server_url = gr.Textbox(
                            label="vLLM服务地址",
                            value=settings.mineru.server_url or "http://127.0.0.1:8000",
                            info="仅 backend=http-client 时使用，指向 OpenAI-compatible vLLM 服务",
                            interactive=True,
                            visible=mineru_default_backend == "http-client",
                        )
                        mineru_dpi = gr.Number(
                            label="DPI",
                            value=settings.mineru.dpi,
                            precision=0,
                            minimum=72,
                            maximum=600,
                            info="仅本地/vLLM后端使用：图像渲染DPI，影响识别质量",
                            visible=mineru_default_backend
                            not in MINERU_ONLINE_BACKENDS,
                        )
                        mineru_timeout_seconds = gr.Number(
                            label="识别/解析超时(秒)",
                            value=settings.mineru.timeout_seconds,
                            precision=0,
                            minimum=0,
                            maximum=7200,
                            info="0表示不限制；本地/vLLM按单页计时，在线API按解析任务计时",
                        )
                        mineru_translation_group_timeout = gr.Number(
                            label="翻译组超时(秒)",
                            value=settings.mineru.translation_group_timeout_seconds,
                            precision=0,
                            minimum=0,
                            maximum=1200,
                            info="0表示不限制；用于外部翻译模型每组请求",
                        )
                        mineru_api_base_url = gr.Textbox(
                            label="MinerU API Base URL",
                            value=settings.mineru.api_base_url,
                            info="官方默认: https://mineru.net",
                            interactive=True,
                            visible=mineru_default_backend in MINERU_ONLINE_BACKENDS,
                        )
                        mineru_api_token = gr.Textbox(
                            label="MinerU精准API Token",
                            value=settings.mineru.api_token or "",
                            type="password",
                            info="仅 online-api 需要；也可用环境变量 MINERU_API_TOKEN",
                            interactive=True,
                            visible=mineru_default_backend == "online-api",
                        )
                        mineru_api_token_save_status = gr.Markdown(
                            value="",
                            visible=False,
                            elem_classes=["secondary-text"],
                        )
                        mineru_api_model_version = gr.Dropdown(
                            label="MinerU精准API模型版本",
                            choices=["vlm", "pipeline", "MinerU-HTML"],
                            value=settings.mineru.api_model_version,
                            info="PDF/图片建议 vlm；HTML 文件才用 MinerU-HTML",
                            interactive=True,
                            visible=mineru_default_backend == "online-api",
                        )
                        mineru_api_language = gr.Textbox(
                            label="MinerU OCR语言包",
                            value=settings.mineru.api_language,
                            info="如 ch/en/japan/korean/chinese_cht/latin/cyrillic 等",
                            interactive=True,
                            visible=mineru_default_backend in MINERU_ONLINE_BACKENDS,
                        )
                        mineru_api_is_ocr = gr.Checkbox(
                            label="启用OCR",
                            value=settings.mineru.api_is_ocr,
                            interactive=True,
                            visible=mineru_default_backend in MINERU_ONLINE_BACKENDS,
                        )
                        mineru_api_enable_formula = gr.Checkbox(
                            label="启用公式识别",
                            value=settings.mineru.api_enable_formula,
                            interactive=True,
                            visible=mineru_default_backend in MINERU_ONLINE_BACKENDS,
                        )
                        mineru_api_enable_table = gr.Checkbox(
                            label="启用表格识别",
                            value=settings.mineru.api_enable_table,
                            interactive=True,
                            visible=mineru_default_backend in MINERU_ONLINE_BACKENDS,
                        )
                        mineru_api_poll_interval = gr.Number(
                            label="在线API轮询间隔(秒)",
                            value=settings.mineru.api_poll_interval_seconds,
                            precision=0,
                            minimum=1,
                            maximum=60,
                            visible=mineru_default_backend in MINERU_ONLINE_BACKENDS,
                        )
                        mineru_api_no_cache = gr.Checkbox(
                            label="精准API绕过缓存",
                            value=settings.mineru.api_no_cache,
                            interactive=True,
                            visible=mineru_default_backend == "online-api",
                        )
                        mineru_api_cache_tolerance = gr.Number(
                            label="精准API缓存容忍时间(秒)",
                            value=settings.mineru.api_cache_tolerance,
                            precision=0,
                            minimum=0,
                            maximum=86400,
                            visible=mineru_default_backend == "online-api",
                        )

                    # ========== 操作按钮 ==========
                    with gr.Row():
                        mineru_translate_btn = gr.Button(
                            "🚀 开始翻译", variant="primary", size="lg"
                        )

                    # ========== 进度和输出 ==========
                    mineru_progress_text = gr.Textbox(
                        label="📊 翻译进度",
                        interactive=False,
                        lines=5,
                    )

                    mineru_output_files = gr.File(
                        label="📥 下载翻译结果", visible=False, file_count="multiple"
                    )

                with gr.Column(scale=1):
                    mineru_pdf_preview_heading = gr.Markdown("## PDF预览")
                    gr.HTML(pdf_preview_toolbar_html("mineru_pdf_preview"))
                    mineru_pdf_preview = PDF(
                        label="PDF预览",
                        visible=False,
                        height=PDF_PREVIEW_RENDER_HEIGHT,
                        elem_id="mineru_pdf_preview",
                        elem_classes=["pdf-viewer-zoomable"],
                    )

                    mineru_markdown_preview_heading = gr.Markdown("## Markdown预览")
                    mineru_markdown_preview = gr.HTML(
                        label="Markdown预览",
                        value="<p style='text-align:center; color:#64748B;'>翻译完成后在这里预览 Markdown；点击历史 Markdown 文件也会在这里显示</p>",
                        visible=True,
                    )

                    mineru_history_heading = gr.Markdown("## 历史记录")
                    mineru_history_initial_rows = refresh_mineru_history()
                    mineru_history_state = gr.State(mineru_history_initial_rows)
                    mineru_history_preview_choice = gr.Radio(
                        label="点击文件预览",
                        choices=_history_choice_labels(mineru_history_initial_rows),
                        value=None,
                        interactive=True,
                        elem_classes=["history-card-picker"],
                    )
                    mineru_history_download_choice = gr.Dropdown(
                        label="下载历史文件",
                        choices=_history_choice_labels(mineru_history_initial_rows),
                        value=None,
                        interactive=True,
                        elem_classes=["history-picker"],
                    )

                    with gr.Row():
                        mineru_refresh_btn = gr.Button("刷新历史记录", size="sm")
                        mineru_history_delete_btn = gr.Button(
                            "删除选中文件", variant="stop", size="sm"
                        )
                        mineru_history_download = gr.DownloadButton(
                            "下载历史文件", visible=False
                        )
                    mineru_history_delete_status = gr.Markdown(value="", visible=False)

            def update_ui_language(language):
                babeldoc_detail_updates = [
                    gr.update(
                        label=engine_field_label(field_name, description, language)
                    )
                    for field_name, description in zip(
                        __gui_service_arg_names,
                        __gui_service_arg_descriptions,
                        strict=False,
                    )
                ]
                mineru_detail_updates = [
                    gr.update(
                        label=engine_field_label(field_name, description, language)
                    )
                    for field_name, description in zip(
                        mineru_translation_engine_arg_names,
                        mineru_translation_engine_arg_descriptions,
                        strict=False,
                    )
                ]
                updates = [
                    gr.update(
                        value=ui_markdown(
                            "## PDF翻译 (BabelDOC)",
                            "## PDF Translation (BabelDOC)",
                            language,
                        )
                    ),
                    gr.update(
                        value=ui_markdown(
                            "### 📁 文件上传", "### 📁 File upload", language
                        )
                    ),
                    gr.update(
                        label=ui_text("输入类型", "Input type", language),
                        choices=file_type_choices(language),
                    ),
                    gr.update(label=ui_text("文件", "File", language)),
                    gr.update(label=ui_text("链接", "Link", language)),
                    gr.update(
                        value=ui_markdown(
                            "### 🔧 翻译引擎", "### 🔧 Translation engine", language
                        )
                    ),
                    gr.update(
                        value=ui_text(
                            "免费翻译服务由 [SiliconFlow](https://siliconflow.cn) 提供",
                            "Free translation service provided by [SiliconFlow](https://siliconflow.cn)",
                            language,
                        )
                    ),
                    gr.update(label=ui_text("翻译引擎", "Service", language)),
                    gr.update(value=ui_text("保存设置", "Save settings", language)),
                    gr.update(value=ui_text("测试连接", "Test connection", language)),
                    gr.update(
                        value=ui_markdown(
                            "### 🌐 翻译设置", "### 🌐 Translation settings", language
                        )
                    ),
                    gr.update(label=ui_text("源语言", "Translate from", language)),
                    gr.update(label=ui_text("目标语言", "Translate to", language)),
                    gr.update(
                        label=ui_text("页码范围", "Pages", language),
                        choices=page_range_choices(language),
                    ),
                    gr.update(
                        label=ui_text(
                            "自定义页码范围（如 1,3,5-10,-5）",
                            "Page range (e.g., 1,3,5-10,-5)",
                            language,
                        ),
                        placeholder=ui_text(
                            "例如：1,3,5-10", "e.g., 1,3,5-10", language
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "输出 PDF 只包含已翻译页",
                            "Only include translated pages in the output PDF.",
                            language,
                        ),
                        info=ui_text(
                            "仅在指定页码范围时生效。",
                            "Effective only when a page range is specified.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text("速率限制模式", "Rate Limit Mode", language),
                        choices=rate_limit_mode_choices(language),
                        info=ui_text(
                            "选择 API 供应商对应的限速方式，点击翻译时会自动换算为 QPS 和线程数。",
                            "Select the rate limit mode that best suits your API provider. Values are converted to QPS and worker count when translation starts.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "RPM（每分钟请求数）", "RPM (Requests Per Minute)", language
                        ),
                        info=ui_text(
                            "多数 API 服务商会提供该参数，例如 OpenAI GPT-4: 500 RPM。",
                            "Most API providers publish this value, such as OpenAI GPT-4: 500 RPM.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text("并发线程数", "Concurrent Threads", language),
                        info=ui_text(
                            "同时处理请求的最大数量。",
                            "Maximum number of requests processed simultaneously.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "QPS（每秒请求数）", "QPS (Queries Per Second)", language
                        ),
                        info=ui_text(
                            "每秒发送的请求数量。",
                            "Number of requests sent per second.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text("最大工作线程数", "Pool Max Workers", language),
                        info=ui_text(
                            "不填或为 0 时，会使用 QPS 作为线程数。",
                            "If unset or 0, QPS will be used as the worker count.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "禁用单语输出", "Disable monolingual output", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "禁用双语输出", "Disable bilingual output", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "双语 PDF 中译文页在前",
                            "Put translated pages first in dual mode",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "双语 PDF 使用原文/译文交替页",
                            "Use alternating pages for dual PDF",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text("水印模式", "Watermark mode", language),
                        choices=watermark_mode_choices(language),
                    ),
                    gr.update(
                        label=ui_text(
                            "自定义翻译提示词",
                            "Custom prompt for translation",
                            language,
                        ),
                        placeholder=ui_text(
                            "给翻译模型的自定义提示词",
                            "Custom prompt for the translator",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "自定义系统提示词", "Custom System Prompt", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "最小翻译文本长度",
                            "Minimum text length to translate",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "文档布局分析 RPC 服务（可选）",
                            "RPC service for document layout analysis (optional)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "禁用自动术语提取",
                            "Disable auto extract glossary",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "保存自动提取的术语表",
                            "Save automatically extracted glossary",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "译文主字体族",
                            "Primary font family for translated text",
                            language,
                        )
                    ),
                    gr.update(label=ui_text("术语表文件", "Glossary File", language)),
                    gr.update(
                        value=ui_markdown(
                            "#### PDF高级选项", "#### PDF advanced options", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "跳过清理（可能提升兼容性）",
                            "Skip clean (maybe improve compatibility)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "禁用富文本翻译（可能提升兼容性）",
                            "Disable rich text translation (maybe improve compatibility)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "增强兼容性（自动启用跳过清理和禁用富文本）",
                            "Enhance compatibility (auto-enables skip_clean and disable_rich_text)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "强制将短行拆成不同段落",
                            "Force split short lines into different paragraphs",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "短行拆分阈值系数",
                            "Split threshold factor for short lines",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "翻译表格文本（实验）",
                            "Translate table text (experimental)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "跳过扫描件检测", "Skip scanned detection", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "OCR 兼容模式（实验，会在后端自动启用跳过扫描件检测）",
                            "OCR workaround (experimental, will auto enable Skip scanned detection in backend)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "自动启用 OCR 兼容模式（适合重度扫描文档）",
                            "Auto enable OCR workaround (enable automatic OCR workaround for heavily scanned documents)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "每个分片最大页数（自动拆分翻译，0 表示不限）",
                            "Maximum pages per part (for auto-split translation, 0 means no limit)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "公式文本字体识别规则（正则，不建议修改）",
                            "Font pattern to identify formula text (regex, not recommended to change)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "公式文本字符识别规则（正则，不建议修改）",
                            "Character pattern to identify formula text (regex, not recommended to change)",
                            language,
                        )
                    ),
                    gr.update(label=ui_text("忽略缓存", "Ignore cache", language)),
                    gr.update(
                        value=ui_markdown(
                            "#### BabelDOC高级选项",
                            "#### BabelDOC advanced options",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "合并交替行号", "Merge alternating line numbers", language
                        ),
                        info=ui_text(
                            "处理带行号文档中的交替行号和正文段落。",
                            "Handle alternating line numbers and text paragraphs in documents with line numbers.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "移除非公式行", "Remove non-formula lines", language
                        ),
                        info=ui_text(
                            "移除段落区域内的非公式行。",
                            "Remove non-formula lines within paragraph areas.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "非公式行 IoU 阈值",
                            "Non-formula line IoU threshold",
                            language,
                        ),
                        info=ui_text(
                            "用于识别非公式行的 IoU 阈值。",
                            "IoU threshold for identifying non-formula lines.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "图表保护阈值",
                            "Figure/table protection threshold",
                            language,
                        ),
                        info=ui_text(
                            "图表区域保护阈值，图表内的线条不会被处理。",
                            "Protection threshold for figures and tables; lines within figures/tables will not be processed.",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "跳过公式偏移计算",
                            "Skip formula offset calculation",
                            language,
                        ),
                        info=ui_text(
                            "处理过程中跳过公式偏移计算。",
                            "Skip formula offset calculation during processing.",
                            language,
                        ),
                    ),
                    gr.update(
                        value=ui_text("🚀 开始翻译", "🚀 Start translation", language)
                    ),
                    gr.update(value=ui_text("⏹️ 取消", "⏹️ Cancel", language)),
                    gr.update(
                        value=ui_markdown(
                            "## 📥 翻译结果", "## 📥 Translation results", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "下载译文 (单语)",
                            "Download translation (monolingual)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "下载译文 (双语)",
                            "Download translation (bilingual)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "下载自动提取的术语表",
                            "Download auto-extracted glossary",
                            language,
                        )
                    ),
                    gr.update(value=ui_markdown("## 预览", "## Preview", language)),
                    gr.update(label=ui_text("PDF预览", "PDF Preview", language)),
                    gr.update(
                        label=ui_text("Markdown 预览", "Markdown Preview", language)
                    ),
                    gr.update(value=ui_markdown("## 历史记录", "## History", language)),
                    gr.update(
                        label=ui_text(
                            "点击文件预览", "Click a file to preview", language
                        )
                    ),
                    gr.update(
                        label=ui_text("下载历史文件", "Download history file", language)
                    ),
                    gr.update(
                        value=ui_text("刷新历史记录", "Refresh history", language)
                    ),
                    gr.update(
                        value=ui_text("删除选中文件", "Delete selected file", language)
                    ),
                    gr.update(
                        value=ui_text("下载历史文件", "Download history file", language)
                    ),
                    gr.update(
                        value=ui_markdown(
                            "## 扫描PDF翻译 (MinerU)",
                            "## Scanned PDF Translation (MinerU)",
                            language,
                        )
                    ),
                    gr.update(
                        value=ui_markdown(
                            "### 📁 文件上传", "### 📁 File upload", language
                        )
                    ),
                    gr.update(
                        label=ui_text("上传PDF文件", "Upload PDF file", language)
                    ),
                    gr.update(
                        value=ui_markdown(
                            "### 🔧 翻译引擎", "### 🔧 Translation engine", language
                        )
                    ),
                    gr.update(
                        value=ui_text(
                            "免费翻译服务由 [SiliconFlow](https://siliconflow.cn) 提供",
                            "Free translation service provided by [SiliconFlow](https://siliconflow.cn)",
                            language,
                        )
                    ),
                    gr.update(label=ui_text("翻译引擎", "Service", language)),
                    gr.update(value=ui_text("保存设置", "Save settings", language)),
                    gr.update(value=ui_text("测试连接", "Test connection", language)),
                    gr.update(
                        value=ui_markdown(
                            "### 🌐 翻译设置", "### 🌐 Translation settings", language
                        )
                    ),
                    gr.update(label=ui_text("源语言", "Translate from", language)),
                    gr.update(label=ui_text("目标语言", "Translate to", language)),
                    gr.update(
                        label=ui_text("输出格式", "Output format", language),
                        info=ui_text(
                            "选择翻译结果的输出格式",
                            "Choose the output format for translated results",
                            language,
                        ),
                        choices=mineru_output_format_choices(language),
                    ),
                    gr.update(
                        label=ui_text("模型路径", "Model path", language),
                        info=ui_text(
                            "仅本地/vLLM后端使用：HuggingFace模型ID或本地路径",
                            "Only for local/vLLM backends: HuggingFace model ID or local path",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text("后端", "Backend", language),
                        info=ui_text(
                            "online-api: 官方精准解析 | online-agent: 官方轻量解析 | http-client: 本地vLLM",
                            "online-api: official precise API | online-agent: official lightweight API | http-client: local vLLM",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text("vLLM服务地址", "vLLM service URL", language),
                        info=ui_text(
                            "仅 backend=http-client 时使用，指向 OpenAI-compatible vLLM 服务",
                            "Only used when backend=http-client; points to an OpenAI-compatible vLLM service",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text("DPI", "DPI", language),
                        info=ui_text(
                            "仅本地/vLLM后端使用：图像渲染DPI，影响识别质量",
                            "Only for local/vLLM backends: image rendering DPI affects recognition quality",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "识别/解析超时(秒)",
                            "Recognition/parse timeout (seconds)",
                            language,
                        ),
                        info=ui_text(
                            "0表示不限制；本地/vLLM按单页计时，在线API按解析任务计时",
                            "0 means no limit; local/vLLM timeout is per page, online API timeout is per parse task",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "翻译组超时(秒)",
                            "Translation group timeout (seconds)",
                            language,
                        ),
                        info=ui_text(
                            "0表示不限制；用于外部翻译模型每组请求",
                            "0 means no limit; used for each grouped request to the translation model",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "MinerU API Base URL", "MinerU API Base URL", language
                        ),
                        info=ui_text(
                            "官方默认: https://mineru.net",
                            "Official default: https://mineru.net",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "MinerU精准API Token", "MinerU precise API token", language
                        ),
                        info=ui_text(
                            "仅 online-api 需要；也可用环境变量 MINERU_API_TOKEN",
                            "Only needed for online-api; MINERU_API_TOKEN environment variable is also supported",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "MinerU精准API模型版本",
                            "MinerU precise API model version",
                            language,
                        ),
                        info=ui_text(
                            "PDF/图片建议 vlm；HTML 文件才用 MinerU-HTML",
                            "Use vlm for PDFs/images; MinerU-HTML is only for HTML files",
                            language,
                        ),
                    ),
                    gr.update(
                        label=ui_text(
                            "MinerU OCR语言包", "MinerU OCR language pack", language
                        ),
                        info=ui_text(
                            "如 ch/en/japan/korean/chinese_cht/latin/cyrillic 等",
                            "Examples: ch/en/japan/korean/chinese_cht/latin/cyrillic",
                            language,
                        ),
                    ),
                    gr.update(label=ui_text("启用OCR", "Enable OCR", language)),
                    gr.update(
                        label=ui_text(
                            "启用公式识别", "Enable formula recognition", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "启用表格识别", "Enable table recognition", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "在线API轮询间隔(秒)",
                            "Online API polling interval (seconds)",
                            language,
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "精准API绕过缓存", "Bypass precise API cache", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "精准API缓存容忍时间(秒)",
                            "Precise API cache tolerance (seconds)",
                            language,
                        )
                    ),
                    gr.update(
                        value=ui_text("🚀 开始翻译", "🚀 Start translation", language)
                    ),
                    gr.update(
                        label=ui_text(
                            "📊 翻译进度", "📊 Translation progress", language
                        )
                    ),
                    gr.update(
                        label=ui_text(
                            "📥 下载翻译结果",
                            "📥 Download translation results",
                            language,
                        )
                    ),
                    gr.update(
                        value=ui_markdown("## PDF预览", "## PDF Preview", language)
                    ),
                    gr.update(label=ui_text("PDF预览", "PDF Preview", language)),
                    gr.update(
                        value=ui_markdown(
                            "## Markdown预览", "## Markdown Preview", language
                        )
                    ),
                    gr.update(
                        label=ui_text("Markdown预览", "Markdown Preview", language)
                    ),
                    gr.update(value=ui_markdown("## 历史记录", "## History", language)),
                    gr.update(
                        label=ui_text(
                            "点击文件预览", "Click a file to preview", language
                        )
                    ),
                    gr.update(
                        label=ui_text("下载历史文件", "Download history file", language)
                    ),
                    gr.update(
                        value=ui_text("刷新历史记录", "Refresh history", language)
                    ),
                    gr.update(
                        value=ui_text("删除选中文件", "Delete selected file", language)
                    ),
                    gr.update(
                        value=ui_text("下载历史文件", "Download history file", language)
                    ),
                ]
                return updates + babeldoc_detail_updates + mineru_detail_updates

            language_switch_outputs = [
                babeldoc_title,
                babeldoc_upload_heading,
                file_type,
                file_input,
                link_input,
                babeldoc_engine_heading,
                siliconflow_free_acknowledgement,
                service,
                babeldoc_engine_save_btn,
                babeldoc_engine_test_btn,
                babeldoc_translation_heading,
                lang_from,
                lang_to,
                page_range,
                page_input,
                only_include_translated_page,
                rate_limit_mode,
                rpm_input,
                concurrent_threads_input,
                custom_qps_input,
                custom_pool_max_workers_input,
                no_mono,
                no_dual,
                dual_translate_first,
                use_alternating_pages_dual,
                watermark_output_mode,
                prompt,
                custom_system_prompt_input,
                min_text_length,
                rpc_doclayout,
                no_auto_extract_glossary,
                save_auto_extracted_glossary,
                primary_font_family,
                glossary_file,
                pdf_advanced_heading,
                skip_clean,
                disable_rich_text_translate,
                enhance_compatibility,
                split_short_lines,
                short_line_split_factor,
                translate_table_text,
                skip_scanned_detection,
                ocr_workaround,
                auto_enable_ocr_workaround,
                max_pages_per_part,
                formular_font_pattern,
                formular_char_pattern,
                ignore_cache,
                babeldoc_advanced_heading,
                merge_alternating_line_numbers,
                remove_non_formula_lines,
                non_formula_line_iou_threshold,
                figure_table_protection_threshold,
                skip_formula_offset_calculation,
                translate_btn,
                cancel_btn,
                output_title,
                output_file_mono,
                output_file_dual,
                output_file_glossary,
                babeldoc_preview_heading,
                preview,
                html_preview,
                babeldoc_history_heading,
                pdf_history_preview_choice,
                pdf_history_download_choice,
                pdf_history_refresh_btn,
                pdf_history_delete_btn,
                pdf_history_download,
                mineru_title,
                mineru_upload_heading,
                mineru_file,
                mineru_engine_heading,
                mineru_siliconflow_free_acknowledgement,
                mineru_service,
                mineru_engine_save_btn,
                mineru_engine_test_btn,
                mineru_translation_heading,
                mineru_lang_from,
                mineru_lang_to,
                mineru_output_format,
                mineru_model_path,
                mineru_backend,
                mineru_server_url,
                mineru_dpi,
                mineru_timeout_seconds,
                mineru_translation_group_timeout,
                mineru_api_base_url,
                mineru_api_token,
                mineru_api_model_version,
                mineru_api_language,
                mineru_api_is_ocr,
                mineru_api_enable_formula,
                mineru_api_enable_table,
                mineru_api_poll_interval,
                mineru_api_no_cache,
                mineru_api_cache_tolerance,
                mineru_translate_btn,
                mineru_progress_text,
                mineru_output_files,
                mineru_pdf_preview_heading,
                mineru_pdf_preview,
                mineru_markdown_preview_heading,
                mineru_markdown_preview,
                mineru_history_heading,
                mineru_history_preview_choice,
                mineru_history_download_choice,
                mineru_refresh_btn,
                mineru_history_delete_btn,
                mineru_history_download,
                *detail_text_inputs,
                *mineru_detail_text_inputs,
            ]

            ui_language.change(
                update_ui_language,
                inputs=[ui_language],
                outputs=language_switch_outputs,
            )

        # ==================== MinerU Tab 事件处理 ====================

        # MinerU Tab的service选择事件处理
        def on_mineru_select_service(service_name):
            """Update MinerU service-specific settings visibility"""
            if not mineru_detail_text_inputs:
                return [gr.update(visible=service_name == "SiliconFlowFree")]

            detail_group_index = mineru_detail_text_input_index_map.get(
                service_name, []
            )
            siliconflow_free_acknowledgement_visible = service_name == "SiliconFlowFree"
            siliconflow_update = [
                gr.update(visible=siliconflow_free_acknowledgement_visible)
            ]

            if len(mineru_detail_text_inputs) == 1:
                return_list = siliconflow_update + [
                    gr.update(visible=(0 in detail_group_index))
                ]
            else:
                return_list = siliconflow_update + [
                    gr.update(visible=(i in detail_group_index))
                    for i in range(len(mineru_detail_text_inputs))
                ]
            return return_list

        def save_mineru_translation_engine_defaults(service_name, *detail_values):
            _persist_translation_engine_gui_defaults(
                service_name,
                mineru_translation_engine_arg_names,
                mineru_translation_engine_arg_service_names,
                detail_values,
            )

        def save_mineru_translation_engine_defaults_with_status(
            service_name, *detail_values
        ):
            ok, message = _persist_translation_engine_gui_defaults(
                service_name,
                mineru_translation_engine_arg_names,
                mineru_translation_engine_arg_service_names,
                detail_values,
            )
            return _translation_engine_status_update(ok, message)

        def test_mineru_translation_engine_connection(service_name, *detail_values):
            ok, message = _test_translation_engine_connection(
                service_name,
                mineru_translation_engine_arg_names,
                mineru_translation_engine_arg_service_names,
                detail_values,
            )
            return _translation_engine_status_update(ok, message)

        def load_mineru_translation_engine_defaults():
            return _load_translation_engine_gui_updates(
                mineru_translation_engine_arg_names,
                mineru_translation_engine_arg_service_names,
            )

        def on_mineru_backend_change(backend_name):
            """Update MinerU backend-specific settings visibility."""
            is_online = backend_name in MINERU_ONLINE_BACKENDS
            is_http_client = backend_name == "http-client"
            is_precise_api = backend_name == "online-api"
            return [
                gr.update(visible=not is_online),  # model_path
                gr.update(visible=is_http_client),  # server_url
                gr.update(visible=not is_online),  # dpi
                gr.update(visible=is_online),  # api_base_url
                gr.update(visible=is_precise_api),  # api_token
                gr.update(visible=is_precise_api),  # api_model_version
                gr.update(visible=is_online),  # api_language
                gr.update(visible=is_online),  # api_is_ocr
                gr.update(visible=is_online),  # api_enable_formula
                gr.update(visible=is_online),  # api_enable_table
                gr.update(visible=is_online),  # api_poll_interval
                gr.update(visible=is_precise_api),  # api_no_cache
                gr.update(visible=is_precise_api),  # api_cache_tolerance
                gr.update(visible=not is_online),  # local setup hint
            ]

        def on_mineru_file_change(file_path):
            if not file_path:
                return gr.update(value=None, visible=False)
            return gr.update(value=file_path, visible=True)

        def save_mineru_api_token(api_token):
            try:
                current_config_manager = ConfigManager()
                cli_env = _initialize_cli_config_for_gui_editing()
                if cli_env.gui_settings.disable_config_auto_save:
                    return gr.update(
                        value="自动保存已关闭，未写入 MinerU Token。", visible=True
                    )

                token_value = str(api_token).strip() if api_token else ""
                cli_env.mineru.api_token = token_value or None
                if token_value and cli_env.mineru.backend not in MINERU_ONLINE_BACKENDS:
                    cli_env.mineru.backend = "online-api"
                cli_env.basic.gui = False
                cli_env.basic.debug = False
                current_config_manager.write_user_default_config_file(settings=cli_env)
                if token_value:
                    return gr.update(
                        value="MinerU Token 已保存，下次打开会自动填入。", visible=True
                    )
                return gr.update(value="MinerU Token 已清空。", visible=True)
            except Exception:
                logger.exception("Failed to save MinerU API token")
                return gr.update(
                    value="MinerU Token 保存失败，请查看日志。", visible=True
                )

        def save_mineru_gui_settings(
            lang_from,
            lang_to,
            model_path,
            backend,
            server_url,
            dpi,
            timeout_seconds,
            translation_group_timeout,
            api_base_url,
            api_token,
            api_model_version,
            api_language,
            api_is_ocr,
            api_enable_formula,
            api_enable_table,
            api_poll_interval,
            api_no_cache,
            api_cache_tolerance,
        ):
            try:
                current_config_manager = ConfigManager()
                cli_env = _initialize_cli_config_for_gui_editing()
                if cli_env.gui_settings.disable_config_auto_save:
                    return

                backend_value = (
                    backend if backend in _mineru_backend_values else "online-api"
                )
                cli_env.translation.lang_in = lang_map.get(lang_from, "en")
                cli_env.translation.lang_out = lang_map.get(lang_to, "zh")
                cli_env.mineru.enabled = True
                cli_env.mineru.backend = backend_value
                cli_env.mineru.model_path = (
                    model_path or "opendatalab/MinerU2.5-Pro-2604-1.2B"
                )
                cli_env.mineru.server_url = (
                    str(server_url).strip() if server_url else None
                )
                cli_env.mineru.dpi = int(dpi) if dpi is not None else 260
                cli_env.mineru.timeout_seconds = (
                    int(timeout_seconds) if timeout_seconds is not None else 600
                )
                cli_env.mineru.translation_group_timeout_seconds = (
                    int(translation_group_timeout)
                    if translation_group_timeout is not None
                    else 300
                )
                cli_env.mineru.api_base_url = (
                    str(api_base_url).strip() if api_base_url else "https://mineru.net"
                )
                cli_env.mineru.api_token = str(api_token).strip() if api_token else None
                cli_env.mineru.api_model_version = api_model_version or "vlm"
                cli_env.mineru.api_language = (
                    str(api_language).strip() if api_language else "ch"
                )
                cli_env.mineru.api_is_ocr = bool(api_is_ocr)
                cli_env.mineru.api_enable_formula = bool(api_enable_formula)
                cli_env.mineru.api_enable_table = bool(api_enable_table)
                cli_env.mineru.api_poll_interval_seconds = (
                    int(api_poll_interval) if api_poll_interval is not None else 3
                )
                cli_env.mineru.api_no_cache = bool(api_no_cache)
                cli_env.mineru.api_cache_tolerance = (
                    int(api_cache_tolerance) if api_cache_tolerance is not None else 900
                )
                cli_env.basic.gui = False
                cli_env.basic.debug = False
                current_config_manager.write_user_default_config_file(settings=cli_env)
            except Exception:
                logger.exception("Failed to save MinerU GUI settings")

        def load_mineru_gui_settings():
            try:
                cli_env = _initialize_cli_config_for_gui_editing()
                mineru = cli_env.mineru
                backend_value = (
                    mineru.backend
                    if mineru.backend in _mineru_backend_values
                    else "online-api"
                )
                is_online = backend_value in MINERU_ONLINE_BACKENDS
                is_http_client = backend_value == "http-client"
                is_precise_api = backend_value == "online-api"
                lang_from_value = rev_lang_map.get(
                    cli_env.translation.lang_in, "English"
                )
                lang_to_value = rev_lang_map.get(
                    cli_env.translation.lang_out, "Simplified Chinese"
                )
                return [
                    gr.update(value=lang_from_value),
                    gr.update(value=lang_to_value),
                    gr.update(value=mineru.model_path, visible=not is_online),
                    gr.update(value=backend_value),
                    gr.update(
                        value=mineru.server_url or "http://127.0.0.1:8000",
                        visible=is_http_client,
                    ),
                    gr.update(value=mineru.dpi, visible=not is_online),
                    gr.update(value=mineru.timeout_seconds),
                    gr.update(value=mineru.translation_group_timeout_seconds),
                    gr.update(value=mineru.api_base_url, visible=is_online),
                    gr.update(value=mineru.api_token or "", visible=is_precise_api),
                    gr.update(value=mineru.api_model_version, visible=is_precise_api),
                    gr.update(value=mineru.api_language, visible=is_online),
                    gr.update(value=mineru.api_is_ocr, visible=is_online),
                    gr.update(value=mineru.api_enable_formula, visible=is_online),
                    gr.update(value=mineru.api_enable_table, visible=is_online),
                    gr.update(
                        value=mineru.api_poll_interval_seconds, visible=is_online
                    ),
                    gr.update(value=mineru.api_no_cache, visible=is_precise_api),
                    gr.update(value=mineru.api_cache_tolerance, visible=is_precise_api),
                    gr.update(visible=not is_online),
                ]
            except Exception:
                logger.exception("Failed to load MinerU GUI settings")
                return [gr.update() for _ in range(19)]

        def persist_mineru_gui_defaults(
            current_config_manager, cli_env, translate_settings
        ):
            if cli_env.gui_settings.disable_config_auto_save:
                return
            cli_env.mineru = translate_settings.mineru.model_copy(deep=True)
            cli_env.translation.lang_in = translate_settings.translation.lang_in
            cli_env.translation.lang_out = translate_settings.translation.lang_out
            cli_env.basic.gui = False
            cli_env.basic.debug = False
            current_config_manager.write_user_default_config_file(settings=cli_env)

        def render_mineru_markdown_preview(output_file_paths):
            if not output_file_paths:
                return gr.update(
                    value="<p style='text-align:center; color:#999;'>未生成可预览文件</p>",
                    visible=True,
                )
            paths = [Path(path) for path in output_file_paths]

            def matches_output_name(path, file_name):
                return path.name == file_name or path.name.endswith(f"_{file_name}")

            md_candidates = [
                path
                for path in paths
                if matches_output_name(path, "translated_self_contained.md")
            ]
            md_candidates += [
                path for path in paths if matches_output_name(path, "translated.md")
            ]
            md_candidates += [
                path
                for path in paths
                if matches_output_name(path, "bilingual_self_contained.md")
            ]
            md_candidates += [
                path for path in paths if matches_output_name(path, "bilingual.md")
            ]
            md_candidates += [path for path in paths if path.suffix.lower() == ".md"]
            html_candidates = [
                path for path in paths if matches_output_name(path, "translated.html")
            ]
            html_candidates += [
                path for path in paths if path.suffix.lower() == ".html"
            ]
            try:
                for path in md_candidates:
                    if path.exists():
                        content = path.read_text(encoding="utf-8")
                        content = embed_markdown_images_as_data_uris(
                            content,
                            base_dirs=[path.parent, path.parent / "images"],
                        )
                        return gr.update(
                            value=MarkdownPreview.generate_single_html(
                                content, title=path.name
                            ),
                            visible=True,
                        )
                for path in html_candidates:
                    if path.exists():
                        return gr.update(
                            value=path.read_text(encoding="utf-8"), visible=True
                        )
            except Exception as e:
                logger.exception("MinerU Markdown preview render failed")
                return gr.update(
                    value=f"<p style='color:#b42318;'>预览渲染失败: {html_lib.escape(str(e))}</p>",
                    visible=True,
                )
            return gr.update(
                value="<p style='text-align:center; color:#999;'>没有找到 Markdown/HTML 预览文件</p>",
                visible=True,
            )

        # 绑定MinerU service选择事件
        if mineru_detail_text_inputs:
            mineru_service.change(
                on_mineru_select_service,
                inputs=[mineru_service],
                outputs=[mineru_siliconflow_free_acknowledgement]
                + mineru_detail_text_inputs,
            )

            mineru_service.change(
                save_mineru_translation_engine_defaults,
                inputs=[mineru_service] + mineru_detail_text_inputs,
            )

            for detail_input in mineru_detail_text_inputs:
                detail_input.change(
                    save_mineru_translation_engine_defaults,
                    inputs=[mineru_service] + mineru_detail_text_inputs,
                )

            mineru_engine_save_btn.click(
                save_mineru_translation_engine_defaults_with_status,
                inputs=[mineru_service] + mineru_detail_text_inputs,
                outputs=[mineru_engine_status],
            )

            mineru_engine_test_btn.click(
                test_mineru_translation_engine_connection,
                inputs=[mineru_service] + mineru_detail_text_inputs,
                outputs=[mineru_engine_status],
            )

            demo.load(
                load_mineru_translation_engine_defaults,
                outputs=[mineru_service, mineru_siliconflow_free_acknowledgement]
                + mineru_detail_text_inputs,
            )

        mineru_backend.change(
            on_mineru_backend_change,
            inputs=[mineru_backend],
            outputs=[
                mineru_model_path,
                mineru_server_url,
                mineru_dpi,
                mineru_api_base_url,
                mineru_api_token,
                mineru_api_model_version,
                mineru_api_language,
                mineru_api_is_ocr,
                mineru_api_enable_formula,
                mineru_api_enable_table,
                mineru_api_poll_interval,
                mineru_api_no_cache,
                mineru_api_cache_tolerance,
                mineru_local_backend_hint,
            ],
        )

        mineru_setting_inputs = [
            mineru_lang_from,
            mineru_lang_to,
            mineru_model_path,
            mineru_backend,
            mineru_server_url,
            mineru_dpi,
            mineru_timeout_seconds,
            mineru_translation_group_timeout,
            mineru_api_base_url,
            mineru_api_token,
            mineru_api_model_version,
            mineru_api_language,
            mineru_api_is_ocr,
            mineru_api_enable_formula,
            mineru_api_enable_table,
            mineru_api_poll_interval,
            mineru_api_no_cache,
            mineru_api_cache_tolerance,
        ]

        for mineru_setting_input in mineru_setting_inputs:
            mineru_setting_input.change(
                save_mineru_gui_settings,
                inputs=mineru_setting_inputs,
            )

        demo.load(
            load_mineru_gui_settings,
            outputs=mineru_setting_inputs + [mineru_local_backend_hint],
        )

        mineru_file.change(
            on_mineru_file_change,
            inputs=[mineru_file],
            outputs=[mineru_pdf_preview],
        )

        mineru_api_token.change(
            save_mineru_api_token,
            inputs=[mineru_api_token],
            outputs=[mineru_api_token_save_status],
        )

        def mineru_translate_handler(
            file_path,
            service,
            lang_from,
            lang_to,
            output_format,
            model_path,
            backend,
            server_url,
            dpi,
            timeout_seconds,
            translation_group_timeout,
            api_base_url,
            api_token,
            api_model_version,
            api_language,
            api_is_ocr,
            api_enable_formula,
            api_enable_table,
            api_poll_interval,
            api_no_cache,
            api_cache_tolerance,
            *translation_engine_args,
            progress=gr.Progress(),
        ):
            """MinerU优化翻译处理函数

            Args:
                file_path: PDF文件路径
                service: 翻译服务名称
                lang_from: 源语言
                lang_to: 目标语言
                output_format: 输出格式 (Markdown/HTML/Both)
                model_path: MinerU模型路径
                backend: MinerU后端 (transformers/http-client/online-api/online-agent)
                server_url: MinerU vLLM HTTP服务地址
                dpi: DPI设置
                *translation_engine_args: 翻译引擎特定参数
                progress: Gradio进度对象
            """
            if not file_path:
                yield (
                    "请先上传PDF文件",
                    gr.update(visible=False),
                    gr.update(visible=True),
                )
                return

            import asyncio
            from pathlib import Path

            project_id = None

            def format_mineru_event(event):
                stage = event.get("stage", "unknown")
                progress_percent = float(event.get("progress") or 0.0)
                message = event.get("message") or ""
                details = event.get("details") or {}
                detail_parts = []
                if isinstance(details, dict):
                    current_group = details.get("current_group")
                    total_groups = details.get("total_groups")
                    if current_group and total_groups:
                        detail_parts.append(f"组 {current_group}/{total_groups}")
                    group_units = details.get("group_units")
                    if group_units:
                        detail_parts.append(f"单元 {group_units}")
                    group_chars = details.get("group_chars")
                    if group_chars:
                        detail_parts.append(f"字符 {group_chars}")
                    elapsed_seconds = details.get("elapsed_seconds")
                    if elapsed_seconds is not None:
                        detail_parts.append(f"耗时 {elapsed_seconds}s")
                    timeout_seconds = details.get("timeout_seconds")
                    if timeout_seconds:
                        detail_parts.append(f"超时阈值 {timeout_seconds}s")
                    status = details.get("status")
                    if status:
                        detail_parts.append(f"状态 {status}")
                detail_text = f" ({'，'.join(detail_parts)})" if detail_parts else ""
                timestamp = datetime.now().strftime("%H:%M:%S")
                return f"[{timestamp}] {stage} {progress_percent:.0%} - {message}{detail_text}\n"

            try:
                progress_text = f"📄 文件: {Path(file_path).name}\n\n"

                # 2. 更新翻译引擎设置
                progress_text += f"🔧 配置翻译引擎: {service}\n"
                progress_text += f"🌐 翻译方向: {lang_from} → {lang_to}\n\n"

                # 获取翻译引擎元数据
                metadata = TRANSLATION_ENGINE_METADATA_MAP.get(service)
                if not metadata:
                    yield (
                        f"❌ 不支持的翻译引擎: {service}",
                        gr.update(visible=False),
                        gr.update(visible=True),
                    )
                    return

                # 使用ConfigManager创建新的配置
                from pdf2zh_next.config import ConfigManager

                config_manager = ConfigManager()

                # 初始化CLI配置
                cli_env = _initialize_cli_config_for_gui_editing()

                # 更新翻译引擎类型：确保仅激活当前选中的翻译服务
                for engine_metadata in TRANSLATION_ENGINE_METADATA:
                    setattr(
                        cli_env,
                        engine_metadata.cli_flag_name,
                        engine_metadata.translate_engine_type == service,
                    )

                # 更新语言设置
                source_lang_code = lang_map.get(lang_from, "en")
                target_lang_code = lang_map.get(lang_to, "zh")
                cli_env.translation.lang_in = source_lang_code
                cli_env.translation.lang_out = target_lang_code

                progress_text += f"  ✓ 源语言: {lang_from} ({source_lang_code})\n"
                progress_text += f"  ✓ 目标语言: {lang_to} ({target_lang_code})\n"

                # 更新翻译引擎特定参数
                if metadata.cli_detail_field_name and translation_engine_args:
                    # 获取引擎详细设置对象
                    if hasattr(cli_env, metadata.cli_detail_field_name):
                        detail_settings = getattr(
                            cli_env, metadata.cli_detail_field_name
                        )
                        translation_arg_values = dict(
                            zip(
                                mineru_translation_engine_arg_names,
                                translation_engine_args,
                                strict=False,
                            )
                        )

                        # 更新引擎特定参数
                        for (
                            field_name,
                            field,
                        ) in metadata.setting_model_type.model_fields.items():
                            if field_name in ["translate_engine_type", "support_llm"]:
                                continue
                            if field.default_factory:
                                continue

                            arg_value = translation_arg_values.get(field_name)
                            if arg_value is not None and arg_value != "":
                                try:
                                    setattr(detail_settings, field_name, arg_value)
                                    display_value = (
                                        "******"
                                        if field_name in GUI_PASSWORD_FIELDS
                                        else arg_value
                                    )
                                    progress_text += (
                                        f"  ✓ {field.description}: {display_value}\n"
                                    )
                                except Exception as e:
                                    progress_text += f"  ⚠ 设置{field_name}失败: {e}\n"

                progress_text += "\n"

                # 转换为SettingsModel，并同步MinerU参数
                translate_settings = cli_env.to_settings_model()

                backend_value = (
                    backend if backend in _mineru_backend_values else "online-api"
                )
                model_value = (
                    model_path if model_path else "opendatalab/MinerU2.5-Pro-2604-1.2B"
                )
                server_url_value = str(server_url).strip() if server_url else ""
                try:
                    dpi_value = int(dpi) if dpi is not None else 260
                except (TypeError, ValueError):
                    dpi_value = 260
                try:
                    timeout_value = (
                        int(timeout_seconds) if timeout_seconds is not None else 600
                    )
                except (TypeError, ValueError):
                    timeout_value = 600
                try:
                    translation_group_timeout_value = (
                        int(translation_group_timeout)
                        if translation_group_timeout is not None
                        else 300
                    )
                except (TypeError, ValueError):
                    translation_group_timeout_value = 300
                try:
                    poll_interval_value = (
                        int(api_poll_interval) if api_poll_interval is not None else 3
                    )
                except (TypeError, ValueError):
                    poll_interval_value = 3
                try:
                    cache_tolerance_value = (
                        int(api_cache_tolerance)
                        if api_cache_tolerance is not None
                        else 900
                    )
                except (TypeError, ValueError):
                    cache_tolerance_value = 900

                api_base_url_value = (
                    str(api_base_url).strip() if api_base_url else "https://mineru.net"
                )
                api_token_value = str(api_token).strip() if api_token else ""
                api_language_value = str(api_language).strip() if api_language else "ch"
                api_model_value = api_model_version or "vlm"

                translate_settings.mineru.enabled = True
                translate_settings.mineru.backend = backend_value
                translate_settings.mineru.model_path = model_value
                translate_settings.mineru.server_url = server_url_value or None
                translate_settings.mineru.dpi = dpi_value
                translate_settings.mineru.timeout_seconds = timeout_value
                translate_settings.mineru.translation_group_timeout_seconds = max(
                    0, translation_group_timeout_value
                )
                translate_settings.mineru.api_base_url = api_base_url_value
                translate_settings.mineru.api_token = api_token_value or None
                translate_settings.mineru.api_model_version = api_model_value
                translate_settings.mineru.api_language = api_language_value
                translate_settings.mineru.api_is_ocr = bool(api_is_ocr)
                translate_settings.mineru.api_enable_formula = bool(api_enable_formula)
                translate_settings.mineru.api_enable_table = bool(api_enable_table)
                translate_settings.mineru.api_poll_interval_seconds = max(
                    1, poll_interval_value
                )
                translate_settings.mineru.api_no_cache = bool(api_no_cache)
                translate_settings.mineru.api_cache_tolerance = max(
                    0, cache_tolerance_value
                )
                translate_settings.validate_settings()
                persist_mineru_gui_defaults(config_manager, cli_env, translate_settings)

                # 创建存储项目，MinerU管线会通过StorageManager落盘结果。
                project_id = storage_manager.create_project(
                    file_path,
                    {
                        "title": Path(file_path).stem,
                        "lang_in": source_lang_code,
                        "lang_out": target_lang_code,
                        "translation_path": "mineru",
                        "output_formats": [output_format],
                    },
                )
                progress_text = f"📋 项目ID: {project_id}\n" + progress_text

                # 3. 创建MinerU优化管道
                progress_text += "🦅 初始化MinerU管道...\n"
                pipeline = MinerUOptimizedPipeline(
                    translate_settings, storage_manager, project_id
                )

                # 4. 配置MinerU参数展示
                progress_text += f"  ✓ 模型: {model_value}\n"
                progress_text += f"  ✓ 后端: {backend_value}\n"
                if backend_value == "http-client":
                    progress_text += f"  ✓ vLLM服务: {server_url_value or 'MINERU_VL_SERVER/MINERU_SERVER_URL'}\n"
                    progress_text += f"  ✓ DPI: {dpi_value}\n"
                elif backend_value == "online-api":
                    progress_text += f"  ✓ MinerU官方精准API: {api_base_url_value}\n"
                    progress_text += f"  ✓ API模型: {api_model_value}\n"
                    progress_text += f"  ✓ API Token: {'已填写/环境变量可用' if (api_token_value or os.getenv('MINERU_API_TOKEN')) else '未填写'}\n"
                elif backend_value == "online-agent":
                    progress_text += (
                        f"  ✓ MinerU官方轻量Agent API: {api_base_url_value}\n"
                    )
                    progress_text += "  ✓ API Token: 不需要\n"
                else:
                    progress_text += f"  ✓ DPI: {dpi_value}\n"
                if backend_value in MINERU_ONLINE_BACKENDS:
                    progress_text += f"  ✓ OCR语言包: {api_language_value}\n"
                    progress_text += f"  ✓ OCR/公式/表格: {bool(api_is_ocr)}/{bool(api_enable_formula)}/{bool(api_enable_table)}\n"
                    progress_text += f"  ✓ 轮询间隔: {max(1, poll_interval_value)}秒\n"
                if backend_value in MINERU_ONLINE_BACKENDS:
                    progress_text += f"  ✓ 解析任务超时: {timeout_value}秒\n\n"
                else:
                    progress_text += (
                        f"  ✓ 单页识别超时: {timeout_value}秒（0表示不限制）\n\n"
                    )
                yield progress_text, gr.update(visible=False), gr.update(visible=True)

                # 5. 执行同步翻译（简化版本）
                try:
                    progress_text += "🚀 开始处理PDF文档...\n\n"
                    yield (
                        progress_text,
                        gr.update(visible=False),
                        gr.update(visible=True),
                    )

                    # 使用同步方式调用异步函数
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        # 处理PDF；输出文件由管线统一生成并保存到StorageManager。
                        event_iterator = pipeline.process_pdf(file_path).__aiter__()
                        last_event_signature = None
                        while True:
                            try:
                                event = loop.run_until_complete(
                                    event_iterator.__anext__()
                                )
                            except StopAsyncIteration:
                                break

                            stage = event.get("stage", "unknown")
                            progress_percent = event.get("progress", 0.0)
                            message = event.get("message", "")
                            details = event.get("details") or {}

                            if progress:
                                progress(progress_percent, desc=f"[{stage}] {message}")

                            event_signature = (
                                stage,
                                round(float(progress_percent or 0.0), 4),
                                message,
                                repr(details),
                            )
                            if event_signature != last_event_signature:
                                progress_text += format_mineru_event(event)
                                yield (
                                    progress_text,
                                    gr.update(visible=False),
                                    gr.update(visible=True),
                                )
                                last_event_signature = event_signature

                            if stage in {"complete", "completed"}:
                                break
                            if stage == "error":
                                raise Exception(message)

                    finally:
                        loop.close()

                    metadata = storage_manager.get_project(project_id)
                    mineru_files = metadata.get("results", {}).get("mineru", [])
                    output_file_paths = []
                    for file_name in mineru_files:
                        if output_format == "Markdown" and file_name.endswith(".html"):
                            continue
                        if output_format == "HTML" and file_name.endswith(".md"):
                            continue
                        file_path_obj = storage_manager.get_file_path(
                            project_id, f"mineru/{file_name}"
                        )
                        if file_path_obj.exists():
                            output_file_paths.append(str(file_path_obj))
                            progress_text += f"  ✓ {file_name}\n"

                    progress_text += (
                        f"\n🎉 翻译完成！共生成 {len(output_file_paths)} 个文件\n"
                    )
                    storage_manager.update_project_status(project_id, "completed")

                    yield (
                        progress_text,
                        gr.update(value=output_file_paths, visible=True),
                        render_mineru_markdown_preview(output_file_paths),
                    )
                    return

                except Exception as e:
                    logger.exception("MinerU processing failed")
                    if project_id:
                        storage_manager.update_project_status(
                            project_id, "failed", error=str(e)
                        )
                    progress_text += f"\n❌ 处理失败: {str(e)}\n"
                    yield (
                        progress_text,
                        gr.update(visible=False),
                        gr.update(visible=True),
                    )
                    return

            except Exception as e:
                logger.exception("MinerU translation failed")
                if project_id:
                    storage_manager.update_project_status(
                        project_id, "failed", error=str(e)
                    )
                error_msg = f"❌ 翻译失败: {str(e)}\n"
                error_msg += f"详细信息: {type(e).__name__}\n"
                yield error_msg, gr.update(visible=False), gr.update(visible=True)
                return

        # 绑定MinerU Tab事件
        mineru_translate_event = mineru_translate_btn.click(
            fn=mineru_translate_handler,
            inputs=[
                mineru_file,
                mineru_service,
                mineru_lang_from,
                mineru_lang_to,
                mineru_output_format,
                mineru_model_path,
                mineru_backend,
                mineru_server_url,
                mineru_dpi,
                mineru_timeout_seconds,
                mineru_translation_group_timeout,
                mineru_api_base_url,
                mineru_api_token,
                mineru_api_model_version,
                mineru_api_language,
                mineru_api_is_ocr,
                mineru_api_enable_formula,
                mineru_api_enable_table,
                mineru_api_poll_interval,
                mineru_api_no_cache,
                mineru_api_cache_tolerance,
            ]
            + mineru_translation_engine_arg_inputs,
            outputs=[
                mineru_progress_text,
                mineru_output_files,
                mineru_markdown_preview,
            ],
        )

        mineru_translate_event.then(
            refresh_mineru_history_picker,
            outputs=[
                mineru_history_preview_choice,
                mineru_history_download_choice,
                mineru_history_state,
                mineru_history_download,
            ],
        )

        mineru_refresh_btn.click(
            fn=refresh_mineru_history_picker,
            outputs=[
                mineru_history_preview_choice,
                mineru_history_download_choice,
                mineru_history_state,
                mineru_history_download,
            ],
        )

        mineru_history_preview_choice.change(
            preview_selected_history_file_only,
            inputs=[mineru_history_state, mineru_history_preview_choice],
            outputs=[mineru_pdf_preview, mineru_markdown_preview],
        )

        mineru_history_download_choice.change(
            selected_history_file_download,
            inputs=[mineru_history_state, mineru_history_download_choice],
            outputs=[mineru_history_download],
        )

        mineru_history_delete_btn.click(
            delete_selected_mineru_history_file,
            inputs=[mineru_history_state, mineru_history_preview_choice],
            outputs=[
                mineru_history_preview_choice,
                mineru_history_download_choice,
                mineru_history_state,
                mineru_history_download,
                mineru_pdf_preview,
                mineru_markdown_preview,
                mineru_history_delete_status,
            ],
        )


def parse_user_passwd(file_path: str, welcome_page: str) -> tuple[list, str]:
    """
    This function parses a user password file.

    Inputs:
        - file_path: The path to the file

    Returns:
        - A tuple containing the user list and HTML
    """
    content = ""
    tuple_list = None
    if welcome_page:
        try:
            path = Path(welcome_page)
            content = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            print(f"Error: File '{welcome_page}' not found.")
    if file_path:
        try:
            path = Path(file_path)
            tuple_list = [
                tuple(line.strip().split(","))
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        except FileNotFoundError:
            tuple_list = None
    return tuple_list, content


def setup_gui(
    share: bool = False,
    auth_file: str | None = None,
    welcome_page: str | None = None,
    server_port=7860,
    inbrowser: bool = True,
    server_name: str | None = None,
) -> None:
    """
    This function sets up the GUI for the application.

    Inputs:
        - share: Whether to share the GUI
        - auth_file: The authentication file
        - server_port: The port to run the server on

    Returns:
        - None
    """

    user_list = None
    html = None

    user_list, html = parse_user_passwd(auth_file, welcome_page)

    preferred_server_name = server_name or "0.0.0.0"

    if not auth_file or not user_list:
        try:
            demo.launch(
                server_name=preferred_server_name,
                debug=True,
                inbrowser=inbrowser,
                share=share,
                server_port=server_port,
                pwa=True,
                allowed_paths=ALLOWED_GUI_PATHS,
            )
        except Exception:
            print(
                f"Error launching GUI using {preferred_server_name}.\nThis may be caused by global mode of proxy software."
            )
            if preferred_server_name == "127.0.0.1":
                raise
            try:
                demo.launch(
                    server_name="127.0.0.1",
                    debug=True,
                    inbrowser=inbrowser,
                    share=share,
                    server_port=server_port,
                    pwa=True,
                    allowed_paths=ALLOWED_GUI_PATHS,
                )
            except Exception:
                print(
                    "Error launching GUI using 127.0.0.1.\nThis may be caused by global mode of proxy software."
                )
                demo.launch(
                    debug=True,
                    inbrowser=inbrowser,
                    share=True,
                    server_port=server_port,
                    pwa=True,
                    allowed_paths=ALLOWED_GUI_PATHS,
                )
    else:
        try:
            demo.launch(
                server_name=preferred_server_name,
                debug=True,
                inbrowser=inbrowser,
                share=share,
                auth=user_list,
                auth_message=html,
                server_port=server_port,
                pwa=True,
                allowed_paths=ALLOWED_GUI_PATHS,
            )
        except Exception:
            print(
                f"Error launching GUI using {preferred_server_name}.\nThis may be caused by global mode of proxy software."
            )
            if preferred_server_name == "127.0.0.1":
                raise
            try:
                demo.launch(
                    server_name="127.0.0.1",
                    debug=True,
                    inbrowser=inbrowser,
                    share=share,
                    auth=user_list,
                    auth_message=html,
                    server_port=server_port,
                    pwa=True,
                    allowed_paths=ALLOWED_GUI_PATHS,
                )
            except Exception:
                print(
                    "Error launching GUI using 127.0.0.1.\nThis may be caused by global mode of proxy software."
                )
                demo.launch(
                    debug=True,
                    inbrowser=inbrowser,
                    share=True,
                    auth=user_list,
                    auth_message=html,
                    server_port=server_port,
                    pwa=True,
                    allowed_paths=ALLOWED_GUI_PATHS,
                )


# For auto-reloading while developing
if __name__ == "__main__":
    from rich.logging import RichHandler

    # disable httpx, openai, httpcore, http11 logs
    logging.getLogger("httpx").setLevel("CRITICAL")
    logging.getLogger("httpx").propagate = False
    logging.getLogger("openai").setLevel("CRITICAL")
    logging.getLogger("openai").propagate = False
    logging.getLogger("httpcore").setLevel("CRITICAL")
    logging.getLogger("httpcore").propagate = False
    logging.getLogger("http11").setLevel("CRITICAL")
    logging.getLogger("http11").propagate = False
    logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])
    setup_gui(inbrowser=False)
