"""MinerU翻译管道 - 修复版本，正确集成原应用翻译引擎

采用方案A: 先完整识别 → 提取文本块 → 批量翻译 → 生成输出

核心优势:
- 与原应用翻译引擎完美集成
- 充分利用缓存机制
- 支持批量优化
- 实现简单清晰
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable

from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.mineru_adapter_fixed import MinerUFixedAdapter
from pdf2zh_next.storage_manager import StorageManager
from pdf2zh_next.translator import get_translator

logger = logging.getLogger(__name__)


class MinerUFixedTranslationPipeline:
    """修复版MinerU翻译管道

    完整翻译流程:
    1. MinerU识别PDF结构
    2. 提取需要翻译的文本块
    3. 使用原应用翻译引擎批量翻译
    4. 生成Markdown/HTML输出
    5. 保存到本地存储
    """

    def __init__(
        self,
        settings: SettingsModel,
        storage_manager: StorageManager,
    ):
        """初始化翻译管道

        Args:
            settings: 应用配置
            storage_manager: 存储管理器
        """
        self.settings = settings
        self.storage = storage_manager

        # 使用原应用的翻译引擎 (关键!)
        try:
            self.translator = get_translator(settings)
            logger.info(f"使用翻译引擎: {self.translator.name}")
        except Exception as e:
            logger.error(f"初始化翻译引擎失败: {e}")
            raise

        # MinerU适配器
        mineru_settings = getattr(settings, 'mineru', None)
        model_path = mineru_settings
        if model_path and hasattr(model_path, 'model_path'):
            model_path = model_path.model_path
        else:
            model_path = "opendatalab/MinerU2.5-Pro-2604-1.2B"

        self.mineru = MinerUFixedAdapter(
            model_path=model_path,
            backend=getattr(mineru_settings, 'backend', 'transformers') if mineru_settings else 'transformers',
            server_url=getattr(mineru_settings, 'server_url', None) if mineru_settings else None,
            dpi=getattr(mineru_settings, 'dpi', 260) if mineru_settings else 260,
        )

        logger.info("MinerU翻译管道初始化完成")

    async def translate_pdf(
        self,
        pdf_path: str | Path,
        project_id: str,
        progress_callback: Optional[Callable] = None,
    ):
        """翻译PDF文件

        Args:
            pdf_path: PDF文件路径
            project_id: 项目ID
            progress_callback: 进度回调函数

        Yields:
            进度事件: {
                'stage': 'extract' | 'prepare' | 'translate' | 'format' | 'complete',
                'progress': 0.0-1.0,
                'message': '状态消息'
            }
        """
        pdf_path = Path(pdf_path)

        try:
            # ========== 阶段1: MinerU识别 (0% - 30%) ==========
            yield {
                "stage": "extract",
                "progress": 0.0,
                "message": "正在使用MinerU识别文档结构..."
            }

            structure = self.mineru.extract_from_pdf(pdf_path)

            yield {
                "stage": "extract",
                "progress": 0.3,
                "message": f"识别完成: {structure['total_pages']} 页, {sum(len(p['blocks']) for p in structure['pages'])} 个内容块"
            }

            # ========== 阶段2: 提取文本块 (30% - 40%) ==========
            yield {
                "stage": "prepare",
                "progress": 0.3,
                "message": "正在提取需要翻译的文本..."
            }

            text_blocks = self._extract_translatable_blocks(structure)

            yield {
                "stage": "prepare",
                "progress": 0.4,
                "message": f"待翻译文本块: {len(text_blocks)}"
            }

            if not text_blocks:
                yield {
                    "stage": "complete",
                    "progress": 1.0,
                    "message": "没有需要翻译的内容"
                }
                return

            # ========== 阶段3: 批量翻译 (40% - 90%) ==========
            yield {
                "stage": "translate",
                "progress": 0.4,
                "message": "正在翻译内容..."
            }

            # 批量翻译
            translated_blocks = await self._translate_blocks(text_blocks)

            yield {
                "stage": "translate",
                "progress": 0.9,
                "message": "翻译完成"
            }

            # ========== 阶段4: 生成输出 (90% - 100%) ==========
            yield {
                "stage": "format",
                "progress": 0.9,
                "message": "正在生成输出文件..."
            }

            # 生成Markdown
            md_translated = self._to_markdown(structure, translated_blocks, mode='translated')
            md_dual = self._to_markdown(structure, translated_blocks, mode='dual')

            # 生成HTML
            html_translated = self._to_html(structure, translated_blocks, mode='translated')
            html_dual = self._to_html(structure, translated_blocks, mode='dual')

            # 保存文件
            self.storage.save_result(project_id, 'mineru', 'translated.md', md_translated)
            self.storage.save_result(project_id, 'mineru', 'dual.md', md_dual)
            self.storage.save_result(project_id, 'mineru', 'translated.html', html_translated)
            self.storage.save_result(project_id, 'mineru', 'dual.html', html_dual)

            # 保存提取的图片
            await self._save_extracted_images(structure, project_id)

            # 更新项目状态
            self.storage.update_project_status(
                project_id,
                'completed',
                total_blocks=len(text_blocks),
                translated_blocks=len(translated_blocks)
            )

            yield {
                "stage": "complete",
                "progress": 1.0,
                "message": "翻译完成！"
            }

        except Exception as e:
            logger.error(f"翻译失败: {e}", exc_info=True)

            # 更新项目状态为失败
            self.storage.update_project_status(
                project_id,
                'failed',
                error=str(e)
            )

            yield {
                "stage": "error",
                "progress": 0.0,
                "message": f"翻译失败: {e}"
            }

    async def _translate_blocks(self, text_blocks: List[Dict[str, Any]]) -> Dict[str, Dict[str, str]]:
        """批量翻译文本块

        Args:
            text_blocks: 文本块列表

        Returns:
            翻译结果字典
        """
        translated_blocks = {}
        total = len(text_blocks)

        for i, block in enumerate(text_blocks):
            try:
                # 使用原应用的翻译引擎
                content = block['content']

                # 调用翻译引擎的translate方法
                if hasattr(self.translator, 'translate'):
                    if asyncio.iscoroutinefunction(self.translator.translate):
                        translated = await self.translator.translate(content)
                    else:
                        translated = self.translator.translate(content)
                else:
                    logger.error(f"翻译引擎 {self.translator} 没有 translate 方法")
                    translated = content  # 翻译失败时返回原文

                translated_blocks[block['id']] = {
                    'original': content,
                    'translated': translated,
                    'type': block['type']
                }

                logger.debug(f"翻译完成: {block['id']} - {content[:50]}...")

            except Exception as e:
                logger.error(f"翻译块 {block['id']} 失败: {e}")
                # 翻译失败时使用原文
                translated_blocks[block['id']] = {
                    'original': block['content'],
                    'translated': block['content'],
                    'type': block['type']
                }

        logger.info(f"批量翻译完成: {len(translated_blocks)}/{total}")
        return translated_blocks

    def _extract_translatable_blocks(self, structure: Dict[str, Any]) -> List[Dict[str, Any]]:
        """提取需要翻译的文本块

        Args:
            structure: MinerU识别的文档结构

        Returns:
            文本块列表
        """
        blocks = []

        for page in structure['pages']:
            page_num = page['page_num']

            for i, block in enumerate(page['blocks']):
                block_type = block.get('type', 'text')

                if block_type == 'text':
                    # 普通文本块
                    content = block.get('content', '').strip()
                    min_length = getattr(self.settings.translation, 'min_text_length', 5)
                    if content and len(content) >= min_length:
                        blocks.append({
                            'id': f"page_{page_num}_block_{i}",
                            'type': 'text',
                            'content': content,
                            'page_num': page_num,
                            'block_index': i
                        })

                elif block_type == 'table':
                    # 表格单元格
                    table_blocks = self._extract_table_cells(block, page_num, i)
                    blocks.extend(table_blocks)

                elif block_type == 'figure':
                    # 图片说明
                    caption = block.get('caption', '').strip()
                    if caption:
                        blocks.append({
                            'id': f"page_{page_num}_block_{i}_caption",
                            'type': 'caption',
                            'content': caption,
                            'page_num': page_num,
                            'block_index': i
                        })

                # formula类型不需要翻译

        logger.info(f"提取了 {len(blocks)} 个需要翻译的文本块")
        return blocks

    def _extract_table_cells(
        self,
        table_block: Dict[str, Any],
        page_num: int,
        block_index: int
    ) -> List[Dict[str, Any]]:
        """从表格中提取需要翻译的单元格"""
        cells = []

        # 尝试从HTML表格中提取文本
        table_html = table_block.get('html', '')
        if table_html:
            import re
            cell_contents = re.findall(r'<t[dh][^>]*>(.*?)</t[dh]>', table_html, re.DOTALL)

            min_length = getattr(self.settings.translation, 'min_text_length', 5)
            for j, content in enumerate(cell_contents):
                # 清理HTML标签
                content = re.sub(r'<[^>]+>', '', content).strip()
                if content and len(content) >= min_length:
                    cells.append({
                        'id': f"page_{page_num}_block_{block_index}_cell_{j}",
                        'type': 'table_cell',
                        'content': content,
                        'page_num': page_num,
                        'block_index': block_index,
                        'cell_index': j
                    })

        return cells

    async def _save_extracted_images(self, structure: Dict[str, Any], project_id: str):
        """保存提取的图片"""
        for page in structure['pages']:
            page_num = page['page_num']

            for i, block in enumerate(page['blocks']):
                if block.get('type') == 'figure' and block.get('image'):
                    try:
                        # 保存图片
                        image_name = f"page_{page_num}_fig_{i}.png"
                        image_path = Path(self.storage.projects_dir) / project_id / "mineru" / "images" / image_name

                        # 确保目录存在
                        image_path.parent.mkdir(parents=True, exist_ok=True)

                        # 保存PIL图片
                        if hasattr(block['image'], 'save'):
                            block['image'].save(image_path)
                            logger.info(f"保存图片: {image_path}")

                    except Exception as e:
                        logger.error(f"保存图片失败: {e}")

    def _to_markdown(
        self,
        structure: Dict[str, Any],
        translated_blocks: Dict[str, Dict[str, str]],
        mode: str = 'translated'
    ) -> str:
        """转换为Markdown格式"""
        md_lines = []

        # 添加文档标题
        md_lines.append(f"# 翻译文档\n")
        md_lines.append(f"> 源语言: {self.settings.translation.lang_in}")
        md_lines.append(f"> 目标语言: {self.settings.translation.lang_out}")
        md_lines.append(f"> 翻译引擎: {self.translator.name}\n")
        md_lines.append("---\n")

        for page in structure['pages']:
            page_num = page['page_num']
            md_lines.append(f"\n## 第 {page_num} 页\n")

            for i, block in enumerate(page['blocks']):
                block_id = f"page_{page_num}_block_{i}"
                block_type = block.get('type', 'text')

                if block_type == 'text':
                    translation = translated_blocks.get(block_id)
                    if translation:
                        if mode == 'dual':
                            md_lines.append(f"> {translation['original']}\n")
                            md_lines.append(f"{translation['translated']}\n")
                        else:
                            md_lines.append(f"{translation['translated']}\n")
                    else:
                        # 未翻译的内容
                        md_lines.append(f"{block.get('content', '')}\n")

                elif block_type == 'formula':
                    latex = block.get('latex', block.get('content', ''))
                    if block.get('inline'):
                        md_lines.append(f"${latex}$")
                    else:
                        md_lines.append(f"\n$$\n{latex}\n$$\n")

                elif block_type == 'table':
                    md_lines.append(self._table_to_markdown(block, translated_blocks, page_num, i, mode))

                elif block_type == 'figure':
                    caption_id = f"{block_id}_caption"
                    caption_translation = translated_blocks.get(caption_id)

                    image_path = f"images/page_{page_num}_fig_{i}.png"

                    if caption_translation:
                        if mode == 'dual':
                            md_lines.append(f"\n![{caption_translation['original']}]({image_path})\n")
                            md_lines.append(f"*原文: {caption_translation['original']}*\n")
                            md_lines.append(f"*译文: {caption_translation['translated']}*\n")
                        else:
                            md_lines.append(f"\n![{caption_translation['translated']}]({image_path})\n")
                            md_lines.append(f"*{caption_translation['translated']}*\n")
                    else:
                        md_lines.append(f"\n![图片]({image_path})\n")

        return '\n'.join(md_lines)

    def _table_to_markdown(
        self,
        table_block: Dict[str, Any],
        translated_blocks: Dict[str, Dict[str, str]],
        page_num: int,
        block_index: int,
        mode: str
    ) -> str:
        """将表格转换为Markdown格式"""
        markdown = table_block.get('markdown', '')
        if markdown:
            return f"\n{markdown}\n"

        return "\n[表格]\n"

    def _to_html(
        self,
        structure: Dict[str, Any],
        translated_blocks: Dict[str, Dict[str, str]],
        mode: str = 'translated'
    ) -> str:
        """转换为HTML格式"""
        # HTML模板
        html_parts = []

        html_parts.append("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>翻译文档</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 30px;
        }
        .page {
            margin-bottom: 40px;
            padding: 20px;
            background: #f9f9f9;
            border-radius: 8px;
        }
        .page-title {
            color: #667eea;
            border-bottom: 2px solid #667eea;
            padding-bottom: 10px;
        }
        .dual-text {
            margin: 15px 0;
            padding: 15px;
            background: white;
            border-left: 4px solid #667eea;
            border-radius: 4px;
        }
        .original {
            color: #666;
            font-style: italic;
            margin-bottom: 10px;
        }
        .translated {
            color: #333;
        }
        .formula {
            text-align: center;
            margin: 20px 0;
            padding: 15px;
            background: #f0f0f0;
            border-radius: 4px;
        }
        img {
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        .caption {
            text-align: center;
            font-style: italic;
            color: #666;
            margin-top: 10px;
        }
    </style>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.0/es5/tex-mml-chtml.js"></script>
</head>
<body>
    <div class="header">
        <h1>翻译文档</h1>
        <p>源语言: """ + self.settings.translation.lang_in + """ → 目标语言: """ + self.settings.translation.lang_out + """</p>
        <p>翻译引擎: """ + self.translator.name + """</p>
    </div>
""")

        # 生成页面内容
        for page in structure['pages']:
            page_num = page['page_num']
            html_parts.append(f'<div class="page"><h2 class="page-title">第 {page_num} 页</h2>')

            for i, block in enumerate(page['blocks']):
                block_id = f"page_{page_num}_block_{i}"
                block_type = block.get('type', 'text')

                if block_type == 'text':
                    translation = translated_blocks.get(block_id)
                    if translation:
                        if mode == 'dual':
                            html_parts.append(f'<div class="dual-text">')
                            html_parts.append(f'<div class="original">{translation["original"]}</div>')
                            html_parts.append(f'<div class="translated">{translation["translated"]}</div>')
                            html_parts.append(f'</div>')
                        else:
                            html_parts.append(f'<p>{translation["translated"]}</p>')

                elif block_type == 'formula':
                    latex = block.get('latex', block.get('content', ''))
                    if block.get('inline'):
                        html_parts.append(f'<span class="formula">\\({latex}\\)</span>')
                    else:
                        html_parts.append(f'<div class="formula">\\[{latex}\\]</div>')

                elif block_type == 'figure':
                    image_path = f"images/page_{page_num}_fig_{i}.png"
                    caption_id = f"{block_id}_caption"
                    caption_translation = translated_blocks.get(caption_id)

                    html_parts.append(f'<img src="{image_path}" alt="图片">')
                    if caption_translation:
                        if mode == 'dual':
                            html_parts.append(f'<div class="caption">原文: {caption_translation["original"]}</div>')
                            html_parts.append(f'<div class="caption">译文: {caption_translation["translated"]}</div>')
                        else:
                            html_parts.append(f'<div class="caption">{caption_translation["translated"]}</div>')

            html_parts.append('</div>')

        html_parts.append('</body></html>')

        return '\n'.join(html_parts)


# 向后兼容的别名
MinerUTranslationPipeline = MinerUFixedTranslationPipeline