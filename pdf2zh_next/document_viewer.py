"""文档浏览器 - 在Gradio中预览各种格式的文档

支持的格式:
- PDF: 转换为图片显示
- Markdown: 渲染为HTML
- HTML: 直接显示
- 文本: 直接显示
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image

logger = logging.getLogger(__name__)


class DocumentViewer:
    """文档浏览器 - 提供多种格式的文档预览功能"""
    
    def __init__(self, max_pdf_pages: int = 10):
        """初始化文档浏览器
        
        Args:
            max_pdf_pages: PDF预览的最大页数，避免加载过大文件
        """
        self.max_pdf_pages = max_pdf_pages
        logger.info(f"文档浏览器初始化: max_pdf_pages={max_pdf_pages}")
    
    def render_pdf(
        self,
        pdf_path: str | Path,
        pages: Optional[List[int]] = None,
        dpi: int = 150
    ) -> List[Image.Image]:
        """将PDF转换为图片列表
        
        Args:
            pdf_path: PDF文件路径
            pages: 要渲染的页码列表，None表示全部页面
            dpi: 渲染DPI，默认150
            
        Returns:
            PIL图片列表
        """
        try:
            import fitz  # PyMuPDF
            
            pdf_path = Path(pdf_path)
            if not pdf_path.exists():
                logger.error(f"PDF文件不存在: {pdf_path}")
                return []
            
            logger.info(f"渲染PDF: {pdf_path}, DPI={dpi}")
            
            images = []
            
            with fitz.open(pdf_path) as doc:
                total_pages = doc.page_count
                
                # 确定要渲染的页面
                if pages is None:
                    pages = list(range(1, min(total_pages + 1, self.max_pdf_pages + 1)))
                else:
                    pages = [p for p in pages if 1 <= p <= total_pages]
                
                logger.info(f"渲染 {len(pages)} 页 (总共 {total_pages} 页)")
                
                for page_num in pages:
                    page = doc[page_num - 1]
                    
                    # 计算缩放比例
                    zoom = dpi / 72.0
                    matrix = fitz.Matrix(zoom, zoom)
                    
                    # 渲染为图片
                    pixmap = page.get_pixmap(matrix=matrix, alpha=False)
                    
                    # 转换为PIL Image
                    import io
                    image_bytes = pixmap.pil_tobytes(format="PNG")
                    image = Image.open(io.BytesIO(image_bytes))
                    
                    images.append(image)
                    
                    logger.debug(f"渲染第 {page_num} 页完成")
            
            logger.info(f"PDF渲染完成: {len(images)} 页")
            return images
            
        except Exception as e:
            logger.error(f"PDF渲染失败: {e}", exc_info=True)
            return []
    
    def render_markdown(
        self,
        md_path: str | Path,
        include_mathjax: bool = True
    ) -> str:
        """将Markdown渲染为HTML
        
        Args:
            md_path: Markdown文件路径
            include_mathjax: 是否包含MathJax支持
            
        Returns:
            HTML字符串
        """
        try:
            md_path = Path(md_path)
            if not md_path.exists():
                logger.error(f"Markdown文件不存在: {md_path}")
                return "<p>文件不存在</p>"
            
            logger.info(f"渲染Markdown: {md_path}")
            
            # 读取Markdown内容
            with open(md_path, 'r', encoding='utf-8') as f:
                md_content = f.read()
            
            # 使用markdown库渲染
            try:
                import markdown
                from markdown.extensions import tables, fenced_code, codehilite
                
                # 配置扩展
                extensions = [
                    'tables',
                    'fenced_code',
                    'codehilite',
                    'nl2br',
                ]
                
                # 渲染Markdown
                html_content = markdown.markdown(
                    md_content,
                    extensions=extensions
                )
                
            except ImportError:
                # 如果没有markdown库，使用简单的替换
                logger.warning("markdown库未安装，使用简单渲染")
                html_content = self._simple_markdown_render(md_content)
            
            # 包装为完整HTML
            html = self._wrap_html(
                html_content,
                title=md_path.name,
                include_mathjax=include_mathjax
            )
            
            logger.info("Markdown渲染完成")
            return html
            
        except Exception as e:
            logger.error(f"Markdown渲染失败: {e}", exc_info=True)
            return f"<p>渲染失败: {e}</p>"
    
    def render_html(self, html_path: str | Path) -> str:
        """读取HTML文件内容
        
        Args:
            html_path: HTML文件路径
            
        Returns:
            HTML字符串
        """
        try:
            html_path = Path(html_path)
            if not html_path.exists():
                logger.error(f"HTML文件不存在: {html_path}")
                return "<p>文件不存在</p>"
            
            logger.info(f"读取HTML: {html_path}")
            
            with open(html_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            logger.info("HTML读取完成")
            return html_content
            
        except Exception as e:
            logger.error(f"HTML读取失败: {e}", exc_info=True)
            return f"<p>读取失败: {e}</p>"
    
    def render_text(self, text_path: str | Path) -> str:
        """读取文本文件内容
        
        Args:
            text_path: 文本文件路径
            
        Returns:
            HTML格式的文本内容
        """
        try:
            text_path = Path(text_path)
            if not text_path.exists():
                logger.error(f"文本文件不存在: {text_path}")
                return "<p>文件不存在</p>"
            
            logger.info(f"读取文本: {text_path}")
            
            with open(text_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            # 转义HTML特殊字符
            import html
            text_content = html.escape(text_content)
            
            # 包装为HTML
            html_content = f"<pre style='white-space: pre-wrap; word-wrap: break-word;'>{text_content}</pre>"
            
            logger.info("文本读取完成")
            return html_content
            
        except Exception as e:
            logger.error(f"文本读取失败: {e}", exc_info=True)
            return f"<p>读取失败: {e}</p>"
    
    def render_file(self, file_path: str | Path) -> Tuple[str, List[Image.Image]]:
        """根据文件类型自动选择渲染方法
        
        Args:
            file_path: 文件路径
            
        Returns:
            (HTML内容, 图片列表) 元组
        """
        file_path = Path(file_path)
        suffix = file_path.suffix.lower()
        
        logger.info(f"自动渲染文件: {file_path} (类型: {suffix})")
        
        if suffix == '.pdf':
            images = self.render_pdf(file_path)
            return "", images
        elif suffix == '.md':
            html = self.render_markdown(file_path)
            return html, []
        elif suffix in ['.html', '.htm']:
            html = self.render_html(file_path)
            return html, []
        elif suffix == '.txt':
            html = self.render_text(file_path)
            return html, []
        else:
            logger.warning(f"不支持的文件类型: {suffix}")
            return f"<p>不支持的文件类型: {suffix}</p>", []
    
    def _simple_markdown_render(self, md_content: str) -> str:
        """简单的Markdown渲染（当markdown库不可用时）
        
        Args:
            md_content: Markdown内容
            
        Returns:
            HTML内容
        """
        import html
        
        lines = md_content.split('\n')
        html_lines = []
        
        for line in lines:
            # 转义HTML
            line = html.escape(line)
            
            # 标题
            if line.startswith('# '):
                html_lines.append(f"<h1>{line[2:]}</h1>")
            elif line.startswith('## '):
                html_lines.append(f"<h2>{line[3:]}</h2>")
            elif line.startswith('### '):
                html_lines.append(f"<h3>{line[4:]}</h3>")
            # 列表
            elif line.startswith('- ') or line.startswith('* '):
                html_lines.append(f"<li>{line[2:]}</li>")
            # 空行
            elif not line.strip():
                html_lines.append("<br>")
            # 普通段落
            else:
                html_lines.append(f"<p>{line}</p>")
        
        return '\n'.join(html_lines)
    
    def _wrap_html(
        self,
        content: str,
        title: str = "文档预览",
        include_mathjax: bool = True
    ) -> str:
        """将内容包装为完整的HTML文档
        
        Args:
            content: HTML内容
            title: 文档标题
            include_mathjax: 是否包含MathJax
            
        Returns:
            完整的HTML文档
        """
        mathjax_script = ""
        if include_mathjax:
            mathjax_script = """
    <script src="https://cdnjs.cloudflare.com/ajax/libs/mathjax/3.2.0/es5/tex-mml-chtml.js"></script>
    <script>
        MathJax = {
            tex: {
                inlineMath: [['$', '$'], ['\\(', '\\)']],
                displayMath: [['$$', '$$'], ['\\[', '\\]']]
            }
        };
    </script>
"""
        
        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 900px;
            margin: 0 auto;
            padding: 20px;
            line-height: 1.6;
            color: #333;
            background: #f9f9f9;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: #2c3e50;
            margin-top: 24px;
            margin-bottom: 16px;
        }}
        h1 {{ font-size: 2em; border-bottom: 2px solid #667eea; padding-bottom: 10px; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #ddd; padding-bottom: 8px; }}
        h3 {{ font-size: 1.25em; }}
        p {{ margin: 12px 0; }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        pre {{
            background: #f4f4f4;
            padding: 12px;
            border-radius: 6px;
            overflow-x: auto;
        }}
        pre code {{
            background: none;
            padding: 0;
        }}
        table {{
            border-collapse: collapse;
            width: 100%;
            margin: 16px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 8px 12px;
            text-align: left;
        }}
        th {{
            background: #667eea;
            color: white;
        }}
        tr:nth-child(even) {{
            background: #f9f9f9;
        }}
        img {{
            max-width: 100%;
            height: auto;
            display: block;
            margin: 20px auto;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        blockquote {{
            border-left: 4px solid #667eea;
            padding-left: 16px;
            margin: 16px 0;
            color: #666;
            font-style: italic;
        }}
        a {{
            color: #667eea;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
        }}
    </style>
    {mathjax_script}
</head>
<body>
    {content}
</body>
</html>
"""
        return html

