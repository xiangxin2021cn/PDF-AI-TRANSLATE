"""MinerU适配器 - 封装MinerU调用接口,提供统一的文档结构提取功能"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

logger = logging.getLogger(__name__)


class MinerUAdapter:
    """MinerU适配器 - 封装MinerU调用,提供文档结构提取功能
    
    功能:
    - 从PDF提取结构化内容(文本、公式、表格、图片)
    - 支持本地transformers和HTTP两种后端
    - 返回统一的文档结构格式
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
            from mineru_standalone.mineru_toolkit.extractor import (
                ExtractionConfig,
                MinerUTableExtractor,
            )
            
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
        
        # 调用MinerU提取
        raw_result = self.extractor.extract_from_pdf(
            pdf_path=pdf_path,
            pages=pages,
            page_range=page_range,
        )
        
        # 转换为统一格式
        structured_result = self._convert_to_unified_format(raw_result)
        
        logger.info(f"提取完成: {len(structured_result['pages'])} 页")
        
        return structured_result
    
    def _convert_to_unified_format(self, raw_result: Dict[str, Any]) -> Dict[str, Any]:
        """将MinerU原始输出转换为统一格式
        
        Args:
            raw_result: MinerU原始输出
            
        Returns:
            统一格式的文档结构
        """
        pages = []
        
        for page_data in raw_result.get('pages', []):
            page_num = page_data.get('page', 1)
            blocks = []
            
            # 处理MinerU的quotas数据
            # 注意: 当前MinerU主要用于表格提取,需要扩展以支持完整文档结构
            # 这里提供一个基础框架,后续可以根据实际MinerU输出调整
            
            quotas = page_data.get('quotas', [])
            for quota in quotas:
                # 根据quota类型转换为block
                block = self._convert_quota_to_block(quota)
                if block:
                    blocks.append(block)
            
            pages.append({
                'page_num': page_num,
                'blocks': blocks,
            })
        
        return {
            'source': raw_result.get('source', ''),
            'total_pages': len(pages),
            'pages': pages,
        }
    
    def _convert_quota_to_block(self, quota: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """将MinerU的quota转换为block
        
        注意: 这是一个简化版本,需要根据实际MinerU输出调整
        """
        # TODO: 根据实际MinerU输出格式实现转换逻辑
        # 当前MinerU主要输出表格数据,需要扩展
        
        return {
            'type': 'table',
            'content': str(quota),
            'bbox': [0, 0, 0, 0],
        }
    
    def extract_from_image(self, image_path: str | Path) -> Dict[str, Any]:
        """从图片提取结构化内容
        
        Args:
            image_path: 图片文件路径
            
        Returns:
            结构化内容
        """
        self.initialize()
        
        logger.info(f"开始提取图片: {image_path}")
        
        raw_result = self.extractor.extract_from_image(image_path=image_path)
        
        # 转换为统一格式
        structured_result = {
            'source': str(image_path),
            'total_pages': 1,
            'pages': [{
                'page_num': 1,
                'blocks': [
                    self._convert_quota_to_block(quota)
                    for quota in raw_result.get('quotas', [])
                ]
            }]
        }
        
        logger.info("图片提取完成")
        
        return structured_result


class MinerUEnhancedAdapter(MinerUAdapter):
    """增强版MinerU适配器
    
    扩展功能:
    - 使用MinerU的two_step_extract直接获取blocks
    - 更完整的文档结构识别
    - 支持文本、公式、表格、图片的完整提取
    """
    
    def extract_from_pdf(
        self,
        pdf_path: str | Path,
        pages: Optional[List[int]] = None,
        page_range: Optional[str] = None,
    ) -> Dict[str, Any]:
        """增强版PDF提取
        
        直接使用MinerU的two_step_extract获取完整blocks
        """
        self.initialize()
        
        import fitz  # PyMuPDF
        from PIL import Image
        import io
        
        logger.info(f"开始增强提取PDF: {pdf_path}")
        
        # 解析页码
        page_numbers = self._resolve_pages(pdf_path, pages, page_range)
        
        result_pages = []
        
        with fitz.open(pdf_path) as document:
            for page_no in page_numbers:
                logger.info(f"处理第 {page_no} 页...")
                
                # 渲染页面为图片
                pil_image = self._render_page(document, page_no)

                # 确保MinerU客户端已加载
                self.extractor._ensure_client_loaded()

                # 使用MinerU提取blocks
                blocks = self.extractor._client.two_step_extract(pil_image)
                
                # 转换blocks为统一格式
                unified_blocks = self._convert_blocks_to_unified(blocks)
                
                result_pages.append({
                    'page_num': page_no,
                    'blocks': unified_blocks,
                })
        
        logger.info(f"增强提取完成: {len(result_pages)} 页")
        
        return {
            'source': str(pdf_path),
            'total_pages': len(result_pages),
            'pages': result_pages,
        }
    
    def _render_page(self, document, page_number: int) -> Image.Image:
        """渲染PDF页面为图片"""
        import fitz
        import io
        
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
        import fitz
        
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
    
    def _convert_blocks_to_unified(self, blocks: List[Any]) -> List[Dict[str, Any]]:
        """将MinerU blocks转换为统一格式"""
        unified_blocks = []
        
        for block in blocks:
            block_type = getattr(block, 'category_type', 'text')
            
            unified_block = {
                'type': self._map_block_type(block_type),
                'content': getattr(block, 'text', ''),
                'bbox': getattr(block, 'bbox', [0, 0, 0, 0]),
                'category': block_type,
            }
            
            # 根据类型添加额外信息
            if block_type == 'formula':
                unified_block['latex'] = getattr(block, 'latex_text', '')
                unified_block['inline'] = getattr(block, 'inline', False)
            elif block_type == 'table':
                unified_block['html'] = getattr(block, 'html', '')
                unified_block['markdown'] = getattr(block, 'markdown', '')
            elif block_type == 'figure':
                unified_block['image'] = getattr(block, 'image', None)
                unified_block['caption'] = getattr(block, 'caption', '')
            
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
        }
        return type_mapping.get(category_type, 'text')

