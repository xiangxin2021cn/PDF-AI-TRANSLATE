"""MinerU适配器 - 修复版本，完整实现MinerU 2.5的功能集成"""
from __future__ import annotations

import logging
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

import fitz  # PyMuPDF
from PIL import Image
import io

logger = logging.getLogger(__name__)


class MinerUFixedAdapter:
    """修复版MinerU适配器 - 完整实现文档结构提取功能

    功能:
    - 从PDF提取结构化内容(文本、公式、表格、图片)
    - 支持本地transformers和HTTP两种后端
    - 返回统一的文档结构格式
    - 正确解析MinerU的实际输出格式
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        backend: str = "transformers",
        server_url: Optional[str] = None,
        dpi: int = 260,
    ):
        """初始化MinerU适配器

        Args:
            model_path: 本地模型路径,默认使用环境变量或配置
            backend: 后端类型,'transformers'(本地)或'http-client'(远程)
            server_url: HTTP服务器URL(仅backend='http-client'时需要)
            dpi: PDF渲染DPI,默认260
        """
        self.model_path = model_path or "opendatalab/MinerU2.5-Pro-2604-1.2B"
        self.backend = backend
        self.server_url = server_url
        self.dpi = dpi
        self.extractor = None

        logger.info(f"初始化MinerU适配器: backend={backend}, model={self.model_path}")

    def initialize(self):
        """初始化MinerU提取器

        延迟加载,避免启动时加载大模型
        """
        if self.extractor is not None:
            return

        try:
            # 尝试导入MinerU
            try:
                from mineru_standalone.mineru_toolkit.extractor import (
                    ExtractionConfig,
                    MinerUTableExtractor,
                )
            except ImportError:
                logger.error("无法导入mineru_standalone，请确保已安装MinerU")
                logger.info("安装命令: pip install mineru-vl-utils[vllm]")
                raise ImportError("MinerU not available")

            config = ExtractionConfig(
                backend=self.backend,
                model_name=self.model_path,
                server_url=self.server_url,
                dpi=self.dpi,
            )

            self.extractor = MinerUTableExtractor(config=config)
            logger.info("MinerU提取器初始化成功")

        except Exception as e:
            logger.error(f"MinerU提取器初始化失败: {e}")
            raise

    def extract_single_page(
        self,
        pdf_path: str | Path,
        page_num: int,
    ) -> Dict[str, Any]:
        """提取单页结构化内容

        Args:
            pdf_path: PDF文件路径
            page_num: 页码(从1开始)

        Returns:
            单页结构化数据
        """
        self.initialize()

        logger.info(f"开始提取第 {page_num} 页: {pdf_path}")

        try:
            with fitz.open(pdf_path) as document:
                # 验证页码有效性
                if page_num < 1 or page_num > document.page_count:
                    raise ValueError(f"页码 {page_num} 超出范围 (1-{document.page_count})")

                logger.info(f"处理第 {page_num} 页，总共 {document.page_count} 页")

                # 渲染页面为图片
                pil_image = self._render_page(document, page_num)

                # 确保MinerU客户端已加载
                self.extractor._ensure_client_loaded()

                # 使用MinerU提取blocks
                try:
                    logger.debug(f"调用MinerU two_step_extract处理第{page_num}页")
                    blocks = self.extractor._client.two_step_extract(pil_image)
                    logger.debug(f"第{page_num}页识别完成，共 {len(blocks)} 个blocks")
                except Exception as e:
                    logger.error(f"MinerU提取第{page_num}页失败: {e}")
                    # 如果MinerU失败，使用基础文本提取
                    blocks = self._fallback_extract(document, page_num)

                # 转换blocks为统一格式
                unified_blocks = self._convert_blocks_to_unified(blocks)
                logger.debug(f"第{page_num}页转换完成，共 {len(unified_blocks)} 个有效blocks")

                page_result = {
                    'page_num': page_num,
                    'blocks': unified_blocks,
                    'raw_blocks': blocks,  # 保留原始blocks用于调试
                    'processing_time': datetime.now().isoformat(),
                }

                logger.info(f"第 {page_num} 页提取完成")
                return page_result

        except Exception as e:
            logger.error(f"提取第 {page_num} 页失败: {e}", exc_info=True)
            raise

    def extract_from_pdf(
        self,
        pdf_path: str | Path,
        pages: Optional[List[int]] = None,
        page_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        """从PDF提取结构化内容

        Args:
            pdf_path: PDF文件路径
            pages: 指定页码列表,如[1, 2, 3]
            page_range: 页码范围字符串,如"1-5,7,9-10"

        Returns:
            {
                'source': 'path/to/file.pdf',
                'total_pages': 10,
                'pages': [
                    {
                        'page_num': 1,
                        'blocks': [
                            {
                                'type': 'text',
                                'content': '文本内容',
                                'bbox': [x1, y1, x2, y2],
                                'category': 'text' | 'title' | 'header' | ...
                            },
                            {
                                'type': 'formula',
                                'content': 'LaTeX公式',
                                'latex': '$$E=mc^2$$',
                                'inline': False,
                                'bbox': [x1, y1, x2, y2]
                            },
                            {
                                'type': 'table',
                                'html': '<table>...</table>',
                                'markdown': '| A | B |\n|---|---|',
                                'cells': [[...]],
                                'bbox': [x1, y1, x2, y2]
                            },
                            {
                                'type': 'figure',
                                'image': PIL.Image,
                                'caption': '图片说明',
                                'bbox': [x1, y1, x2, y2]
                            }
                        ]
                    }
                ]
            }
        """
        self.initialize()

        logger.info(f"开始提取PDF: {pdf_path}")

        # 解析页码
        page_numbers = self._resolve_pages(pdf_path, pages, page_range)

        result_pages = []

        for page_no in page_numbers:
            try:
                page_result = self.extract_single_page(pdf_path, page_no)
                result_pages.append(page_result)
            except Exception as e:
                logger.error(f"处理第 {page_no} 页失败，跳过: {e}")
                # 添加空页面结果以保持页面连续性
                result_pages.append({
                    'page_num': page_no,
                    'blocks': [],
                    'error': str(e)
                })

        logger.info(f"PDF提取完成: {len(result_pages)} 页，成功处理 {len([p for p in result_pages if 'error' not in p])} 页")

        return {
            'source': str(pdf_path),
            'total_pages': len(result_pages),
            'pages': result_pages,
        }

    def _render_page(self, document, page_number: int) -> Image.Image:
        """渲染PDF页面为图片"""
        page = document[page_number - 1]
        zoom = self.dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix, alpha=False)
        image_bytes = pixmap.pil_tobytes(format="PNG")
        return Image.open(io.BytesIO(image_bytes))

    def _resolve_pages(
        self,
        pdf_path: str | Path,
        explicit_pages: Optional[List[int]],
        range_expr: Optional[str],
    ) -> List[int]:
        """解析页码范围"""
        with fitz.open(pdf_path) as document:
            total = document.page_count

        if explicit_pages:
            return [p for p in explicit_pages if 1 <= p <= total]

        if range_expr:
            selected = []
            for chunk in range_expr.split(','):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if '-' in chunk:
                    start, end = chunk.split('-', 1)
                    selected.extend(range(int(start), int(end) + 1))
                else:
                    selected.append(int(chunk))
            return [p for p in selected if 1 <= p <= total]

        return list(range(1, total + 1))

    def _fallback_extract(self, document, page_number: int) -> List[Any]:
        """MinerU失败时的基础文本提取"""
        page = document[page_number - 1]
        text = page.get_text()

        # 创建简单的文本block
        class SimpleBlock:
            def __init__(self, text):
                self.text = text
                self.category_type = 'text'
                self.bbox = [0, 0, 0, 0]

        return [SimpleBlock(text)] if text.strip() else []

    def _convert_blocks_to_unified(self, blocks: List[Any]) -> List[Dict[str, Any]]:
        """将MinerU blocks转换为统一格式"""
        unified_blocks = []

        for i, block in enumerate(blocks):
            if isinstance(block, dict):
                block_type = block.get('category_type') or block.get('type', 'text')
                content = block.get('content') or block.get('text') or ''
                bbox = block.get('bbox', [0, 0, 0, 0])
            else:
                if not hasattr(block, 'category_type'):
                    continue
                block_type = getattr(block, 'category_type', 'text')
                content = getattr(block, 'text', '')
                bbox = getattr(block, 'bbox', [0, 0, 0, 0])

            unified_block = {
                'type': self._map_block_type(block_type),
                'content': content,
                'bbox': bbox,
                'category': block_type,
            }

            # 根据类型添加额外信息
            if block_type == 'formula':
                unified_block['latex'] = block.get('latex', '') if isinstance(block, dict) else getattr(block, 'latex_text', '')
                unified_block['inline'] = block.get('inline', False) if isinstance(block, dict) else getattr(block, 'inline', False)
            elif block_type == 'table':
                unified_block['html'] = block.get('html', '') if isinstance(block, dict) else getattr(block, 'html', '')
                unified_block['markdown'] = block.get('markdown', '') if isinstance(block, dict) else getattr(block, 'markdown', '')
                unified_block['cells'] = block.get('cells', []) if isinstance(block, dict) else getattr(block, 'cells', [])
            elif block_type == 'figure':
                unified_block['image'] = block.get('image') if isinstance(block, dict) else getattr(block, 'image', None)
                unified_block['caption'] = block.get('caption', '') if isinstance(block, dict) else getattr(block, 'caption', '')

            unified_blocks.append(unified_block)

        return unified_blocks

    def _map_block_type(self, category_type: str) -> str:
        """映射MinerU的category_type到统一类型"""
        type_mapping = {
            'text': 'text',
            'title': 'text',
            'header': 'text',
            'formula': 'formula',
            'table': 'table',
            'table_caption': 'text',
            'table_footnote': 'text',
            'figure': 'figure',
            'figure_caption': 'text',
            'list': 'text',
            'caption': 'text',
        }
        return type_mapping.get(category_type, 'text')

    def extract_from_image(self, image_path: str | Path) -> Dict[str, Any]:
        """从图片提取结构化内容

        Args:
            image_path: 图片文件路径

        Returns:
            结构化内容
        """
        self.initialize()

        logger.info(f"开始提取图片: {image_path}")

        try:
            # 加载图片
            image = Image.open(image_path)

            # 确保MinerU客户端已加载
            self.extractor._ensure_client_loaded()

            # 使用MinerU提取blocks
            blocks = self.extractor._client.two_step_extract(image)

            # 转换为统一格式
            unified_blocks = self._convert_blocks_to_unified(blocks)

            result = {
                'source': str(image_path),
                'total_pages': 1,
                'pages': [{
                    'page_num': 1,
                    'blocks': unified_blocks,
                }]
            }

            logger.info("图片提取完成")
            return result

        except Exception as e:
            logger.error(f"图片提取失败: {e}", exc_info=True)
            return {
                'source': str(image_path),
                'total_pages': 0,
                'pages': [],
            }


# 向后兼容的别名
MinerUAdapter = MinerUFixedAdapter
MinerUEnhancedAdapter = MinerUFixedAdapter