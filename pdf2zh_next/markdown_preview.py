#!/usr/bin/env python3
"""
Markdown预览组件
提供原文和译文的对比预览功能
"""

import logging
import re
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

class MarkdownPreview:
    """Markdown预览生成器"""
    @staticmethod
    def generate_single_html(markdown_content: str, title: str = "Markdown Preview") -> str:
        """生成单个Markdown文件的渲染预览HTML。"""
        rendered_html = MarkdownPreview._markdown_to_html(markdown_content)
        return f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.62;
            margin: 0;
            padding: 18px;
            color: #24292f;
            background: #fff;
        }}
        .markdown-preview {{
            max-width: 1180px;
            margin: 0 auto;
        }}
        h1, h2, h3, h4, h5, h6 {{
            color: #1f2328;
            margin-top: 22px;
            margin-bottom: 12px;
            line-height: 1.25;
        }}
        h1 {{ font-size: 1.9em; border-bottom: 1px solid #d8dee4; padding-bottom: 8px; }}
        h2 {{ font-size: 1.45em; border-bottom: 1px solid #d8dee4; padding-bottom: 6px; }}
        h3 {{ font-size: 1.18em; }}
        p {{ margin: 0 0 12px; }}
        table {{
            border-collapse: collapse;
            width: auto;
            max-width: 100%;
            margin: 12px 0 18px;
            overflow: auto;
            display: block;
        }}
        th, td {{
            border: 1px solid #d0d7de;
            padding: 7px 10px;
            vertical-align: top;
            text-align: left;
        }}
        th {{ background: #f6f8fa; font-weight: 600; }}
        blockquote {{
            border-left: 4px solid #d0d7de;
            color: #57606a;
            margin: 12px 0;
            padding: 0 12px;
        }}
        code {{
            background: #f6f8fa;
            border-radius: 4px;
            padding: 2px 4px;
            font-family: Consolas, "SFMono-Regular", Menlo, monospace;
            font-size: 0.92em;
        }}
        pre {{ background: #f6f8fa; padding: 12px; border-radius: 6px; overflow: auto; }}
        pre code {{ padding: 0; background: transparent; }}
        img {{ max-width: 100%; height: auto; }}
        hr {{ border: 0; border-top: 1px solid #d8dee4; margin: 18px 0; }}
    </style>
</head>
<body>
    <article class="markdown-preview">
        {rendered_html}
    </article>
</body>
</html>
        """
    
    @staticmethod
    def generate_comparison_html(original_content: str, translated_content: str, title: str = "Markdown Translation") -> str:
        """
        生成原文和译文对比的HTML
        
        Args:
            original_content: 原始Markdown内容
            translated_content: 翻译后的Markdown内容
            title: 页面标题
            
        Returns:
            HTML字符串
        """
        
        # 转换Markdown为HTML（简单实现）
        original_html = MarkdownPreview._markdown_to_html(original_content)
        translated_html = MarkdownPreview._markdown_to_html(translated_content)
        
        html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }}
        
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        
        .content {{
            display: flex;
            min-height: 600px;
        }}
        
        .panel {{
            flex: 1;
            padding: 20px;
            overflow-y: auto;
            max-height: 80vh;
        }}
        
        .panel-header {{
            background: #f8f9fa;
            margin: -20px -20px 20px -20px;
            padding: 15px 20px;
            border-bottom: 1px solid #e9ecef;
            font-weight: bold;
            color: #495057;
        }}
        
        .original {{
            border-right: 1px solid #e9ecef;
        }}
        
        .translated {{
            background: #f8fff8;
        }}
        
        /* Markdown样式 */
        h1, h2, h3, h4, h5, h6 {{
            color: #333;
            margin-top: 24px;
            margin-bottom: 16px;
        }}
        
        h1 {{ font-size: 2em; border-bottom: 1px solid #eaecef; padding-bottom: 10px; }}
        h2 {{ font-size: 1.5em; border-bottom: 1px solid #eaecef; padding-bottom: 8px; }}
        h3 {{ font-size: 1.25em; }}
        
        p {{
            margin-bottom: 16px;
            color: #24292e;
        }}
        
        code {{
            background: #f6f8fa;
            border-radius: 3px;
            padding: 2px 4px;
            font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
            font-size: 85%;
        }}
        
        pre {{
            background: #f6f8fa;
            border-radius: 6px;
            padding: 16px;
            overflow: auto;
            line-height: 1.45;
        }}
        
        pre code {{
            background: transparent;
            padding: 0;
        }}
        
        blockquote {{
            border-left: 4px solid #dfe2e5;
            padding: 0 16px;
            color: #6a737d;
            margin: 0 0 16px 0;
        }}
        
        ul, ol {{
            padding-left: 30px;
            margin-bottom: 16px;
        }}
        
        li {{
            margin-bottom: 4px;
        }}
        
        table {{
            border-collapse: collapse;
            width: 100%;
            margin-bottom: 16px;
        }}
        
        th, td {{
            border: 1px solid #dfe2e5;
            padding: 8px 12px;
            text-align: left;
        }}
        
        th {{
            background: #f6f8fa;
            font-weight: bold;
        }}
        
        .sync-scroll {{
            cursor: pointer;
            background: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            margin: 10px;
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
        }}
        
        .sync-scroll:hover {{
            background: #0056b3;
        }}
        
        @media (max-width: 768px) {{
            .content {{
                flex-direction: column;
            }}
            
            .panel {{
                max-height: 50vh;
            }}
            
            .original {{
                border-right: none;
                border-bottom: 1px solid #e9ecef;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
        </div>
        
        <button class="sync-scroll" onclick="toggleSyncScroll()" id="syncBtn">同步滚动: 开启</button>
        
        <div class="content">
            <div class="panel original" id="originalPanel">
                <div class="panel-header">📄 原文</div>
                <div class="markdown-content">
                    {original_html}
                </div>
            </div>
            
            <div class="panel translated" id="translatedPanel">
                <div class="panel-header">🌐 译文</div>
                <div class="markdown-content">
                    {translated_html}
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let syncScrollEnabled = true;
        let isScrolling = false;
        
        const originalPanel = document.getElementById('originalPanel');
        const translatedPanel = document.getElementById('translatedPanel');
        const syncBtn = document.getElementById('syncBtn');
        
        function toggleSyncScroll() {{
            syncScrollEnabled = !syncScrollEnabled;
            syncBtn.textContent = syncScrollEnabled ? '同步滚动: 开启' : '同步滚动: 关闭';
            syncBtn.style.background = syncScrollEnabled ? '#007bff' : '#6c757d';
        }}
        
        function syncScroll(source, target) {{
            if (!syncScrollEnabled || isScrolling) return;
            
            isScrolling = true;
            const scrollPercentage = source.scrollTop / (source.scrollHeight - source.clientHeight);
            target.scrollTop = scrollPercentage * (target.scrollHeight - target.clientHeight);
            
            setTimeout(() => {{
                isScrolling = false;
            }}, 50);
        }}
        
        originalPanel.addEventListener('scroll', () => syncScroll(originalPanel, translatedPanel));
        translatedPanel.addEventListener('scroll', () => syncScroll(translatedPanel, originalPanel));
    </script>
</body>
</html>
        """
        
        return html_template
    
    @staticmethod
    def _markdown_to_html(markdown_content: str) -> str:
        """
        简单的Markdown到HTML转换
        这是一个基础实现，可以根据需要扩展
        """
        try:
            import markdown

            return markdown.markdown(
                markdown_content,
                extensions=["extra", "tables", "fenced_code", "nl2br", "sane_lists"],
                output_format="html5",
            )
        except Exception as e:
            logger.debug("Python-Markdown渲染失败，使用简化渲染: %s", e)

        html = markdown_content
        
        # 转义HTML特殊字符
        html = html.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        
        # 代码块
        html = re.sub(r'```(\w+)?\n(.*?)\n```', r'<pre><code>\2</code></pre>', html, flags=re.DOTALL)
        html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)
        
        # 标题
        html = re.sub(r'^# (.*$)', r'<h1>\1</h1>', html, flags=re.MULTILINE)
        html = re.sub(r'^## (.*$)', r'<h2>\1</h2>', html, flags=re.MULTILINE)
        html = re.sub(r'^### (.*$)', r'<h3>\1</h3>', html, flags=re.MULTILINE)
        html = re.sub(r'^#### (.*$)', r'<h4>\1</h4>', html, flags=re.MULTILINE)
        html = re.sub(r'^##### (.*$)', r'<h5>\1</h5>', html, flags=re.MULTILINE)
        html = re.sub(r'^###### (.*$)', r'<h6>\1</h6>', html, flags=re.MULTILINE)
        
        # 粗体和斜体
        html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
        html = re.sub(r'\*(.*?)\*', r'<em>\1</em>', html)
        
        # 链接
        html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)
        
        # 引用
        html = re.sub(r'^> (.*$)', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
        
        # 列表
        lines = html.split('\n')
        result_lines = []
        in_ul = False
        in_ol = False
        
        for line in lines:
            # 无序列表
            if re.match(r'^\s*[-*+]\s', line):
                if not in_ul:
                    if in_ol:
                        result_lines.append('</ol>')
                        in_ol = False
                    result_lines.append('<ul>')
                    in_ul = True
                item_text = re.sub(r'^\s*[-*+]\s', '', line)
                result_lines.append(f'<li>{item_text}</li>')
            # 有序列表
            elif re.match(r'^\s*\d+\.\s', line):
                if not in_ol:
                    if in_ul:
                        result_lines.append('</ul>')
                        in_ul = False
                    result_lines.append('<ol>')
                    in_ol = True
                item_text = re.sub(r'^\s*\d+\.\s', '', line)
                result_lines.append(f'<li>{item_text}</li>')
            else:
                if in_ul:
                    result_lines.append('</ul>')
                    in_ul = False
                if in_ol:
                    result_lines.append('</ol>')
                    in_ol = False
                result_lines.append(line)
        
        # 关闭未关闭的列表
        if in_ul:
            result_lines.append('</ul>')
        if in_ol:
            result_lines.append('</ol>')
        
        html = '\n'.join(result_lines)
        
        # 表格（简单实现）
        lines = html.split('\n')
        result_lines = []
        in_table = False
        
        for i, line in enumerate(lines):
            if '|' in line and line.strip():
                if not in_table:
                    result_lines.append('<table>')
                    in_table = True
                
                # 检查是否是分隔行
                if re.match(r'^[\s|:-]+$', line.strip()):
                    continue
                
                cells = [cell.strip() for cell in line.split('|')]
                if cells[0] == '':
                    cells = cells[1:]
                if cells and cells[-1] == '':
                    cells = cells[:-1]
                
                # 判断是否是表头
                is_header = False
                if i + 1 < len(lines) and re.match(r'^[\s|:-]+$', lines[i + 1].strip()):
                    is_header = True
                
                if is_header:
                    result_lines.append('<tr>')
                    for cell in cells:
                        result_lines.append(f'<th>{cell}</th>')
                    result_lines.append('</tr>')
                else:
                    result_lines.append('<tr>')
                    for cell in cells:
                        result_lines.append(f'<td>{cell}</td>')
                    result_lines.append('</tr>')
            else:
                if in_table:
                    result_lines.append('</table>')
                    in_table = False
                result_lines.append(line)
        
        if in_table:
            result_lines.append('</table>')
        
        html = '\n'.join(result_lines)
        
        # 段落
        paragraphs = html.split('\n\n')
        result_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if para and not para.startswith('<'):
                # 不是HTML标签开头的段落
                if '\n' in para:
                    # 多行段落，保持换行
                    para = para.replace('\n', '<br>')
                result_paragraphs.append(f'<p>{para}</p>')
            else:
                result_paragraphs.append(para)
        
        html = '\n\n'.join(result_paragraphs)
        
        return html
    
    @staticmethod
    def save_preview_file(original_content: str, translated_content: str, output_path: Path, title: str = "Markdown Translation") -> Path:
        """
        保存预览HTML文件
        
        Args:
            original_content: 原始内容
            translated_content: 翻译内容
            output_path: 输出路径
            title: 页面标题
            
        Returns:
            保存的HTML文件路径
        """
        html_content = MarkdownPreview.generate_comparison_html(original_content, translated_content, title)
        
        preview_path = output_path.parent / f"{output_path.stem}_preview.html"
        preview_path.write_text(html_content, encoding='utf-8')
        
        logger.info(f"预览文件已保存到: {preview_path}")
        return preview_path
