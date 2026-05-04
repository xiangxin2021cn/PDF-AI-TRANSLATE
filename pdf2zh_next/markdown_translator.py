import re
import asyncio
from pathlib import Path
from typing import Dict, List, Tuple, Any
import logging

logger = logging.getLogger(__name__)

def extract_markdown_elements(content: str) -> List[Tuple[str, str, int]]:
    """
    提取Markdown文档中的各种元素
    
    Args:
        content: Markdown文档内容
        
    Returns:
        List of tuples: (element_type, content, line_number)
    """
    elements = []
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        line_num = i + 1
        
        # 标题
        if re.match(r'^#{1,6}\s+', line):
            elements.append(('header', line, line_num))
        # 代码块开始/结束
        elif re.match(r'^```', line):
            elements.append(('code_fence', line, line_num))
        # 列表项
        elif re.match(r'^[\s]*[-*+]\s+', line) or re.match(r'^[\s]*\d+\.\s+', line):
            elements.append(('list_item', line, line_num))
        # 引用
        elif re.match(r'^>\s*', line):
            elements.append(('quote', line, line_num))
        # 表格
        elif '|' in line and line.strip():
            elements.append(('table_row', line, line_num))
        # 链接定义
        elif re.match(r'^\[.+\]:\s*', line):
            elements.append(('link_def', line, line_num))
        # 空行
        elif not line.strip():
            elements.append(('empty', line, line_num))
        # 普通文本
        else:
            elements.append(('text', line, line_num))
    
    return elements

def translate_text_content(text: str, translator_func) -> str:
    """
    翻译文本内容，保留Markdown语法
    
    Args:
        text: 要翻译的文本
        translator_func: 翻译函数
        
    Returns:
        翻译后的文本
    """
    if not text.strip():
        return text
    
    # 保护Markdown语法元素
    protected_patterns = [
        (r'`([^`]+)`', '`{}`'),  # 行内代码
        (r'\[([^\]]+)\]\(([^)]+)\)', '[{}]({})'),  # 链接
        (r'!\[([^\]]*)\]\(([^)]+)\)', '![{}]({})'),  # 图片
        (r'\*\*([^*]+)\*\*', '**{}**'),  # 粗体
        (r'\*([^*]+)\*', '*{}*'),  # 斜体
        (r'~~([^~]+)~~', '~~{}~~'),  # 删除线
    ]
    
    # 提取需要保护的内容
    protected_content = []
    working_text = text
    
    for pattern, template in protected_patterns:
        matches = re.finditer(pattern, working_text)
        for match in reversed(list(matches)):
            placeholder = f"__PROTECTED_{len(protected_content)}__"
            protected_content.append((placeholder, match.group(0)))
            working_text = working_text[:match.start()] + placeholder + working_text[match.end():]
    
    # 翻译处理后的文本
    if working_text.strip():
        translated_text = translator_func(working_text)
    else:
        translated_text = working_text
    
    # 恢复保护的内容
    for placeholder, original in reversed(protected_content):
        translated_text = translated_text.replace(placeholder, original)
    
    return translated_text

def get_translator_function(settings):
    """
    根据设置获取真正的翻译器

    Args:
        settings: 翻译设置

    Returns:
        翻译器函数
    """
    from pdf2zh_next.translator.utils import get_translator

    # 获取真正的翻译器实例，如果失败直接抛出异常
    translator = get_translator(settings)
    logger.info(f"成功初始化翻译器: {type(translator).__name__}")
    logger.info(f"翻译语言: {settings.translation.lang_in} -> {settings.translation.lang_out}")

    def translate_func(text: str) -> str:
        """翻译函数包装器"""
        if not text.strip():
            return text

        # 调用真正的翻译器，如果失败直接抛出异常
        result = translator.translate(text)
        logger.debug(f"翻译成功: '{text[:50]}...' -> '{result[:50]}...'")
        return result

    return translate_func

async def translate_markdown_file(
    file_path: Path,
    settings,
    progress=None
) -> str:
    """
    异步翻译Markdown文件

    Args:
        file_path: Markdown文件路径
        settings: 翻译设置
        progress: 进度回调函数

    Returns:
        翻译后的Markdown内容
    """
    try:
        logger.info(f"开始翻译Markdown文件: {file_path}")

        if progress:
            progress(0.1, desc="读取Markdown文件...")

        # 读取文件内容
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        content = file_path.read_text(encoding='utf-8')
        logger.info(f"文件读取成功，内容长度: {len(content)} 字符")

        if progress:
            progress(0.2, desc="解析Markdown结构...")

        # 提取Markdown元素
        elements = extract_markdown_elements(content)
        logger.info(f"解析完成，共 {len(elements)} 个元素")

        if progress:
            progress(0.3, desc="初始化翻译器...")

        # 获取翻译函数
        translator_func = get_translator_function(settings)
        logger.info("翻译器初始化完成")

        if progress:
            progress(0.5, desc="收集需要翻译的文本...")

        # 收集所有需要翻译的文本，批量处理
        texts_to_translate = []
        text_mapping = {}  # 存储原文到索引的映射

        translated_lines = []
        in_code_block = False

        # 第一遍：收集需要翻译的文本
        for element_type, line_content, line_num in elements:
            if element_type == 'code_fence':
                in_code_block = not in_code_block
                continue
            elif in_code_block or element_type in ['empty', 'link_def']:
                continue

            # 提取需要翻译的文本
            text_to_translate = None
            if element_type == 'header':
                match = re.match(r'^#{1,6}\s+(.+)', line_content)
                if match:
                    text_to_translate = match.group(1)
            elif element_type == 'list_item':
                match = re.match(r'^\s*[-*+]\s+(.+)|^\s*\d+\.\s+(.+)', line_content)
                if match:
                    text_to_translate = match.group(1) or match.group(2)
            elif element_type == 'quote':
                match = re.match(r'^>\s*(.+)', line_content)
                if match:
                    text_to_translate = match.group(1)
            elif element_type == 'table_row':
                if not re.match(r'^[\s|:-]+$', line_content):
                    # 提取表格单元格文本
                    cells = [cell.strip() for cell in line_content.split('|') if cell.strip()]
                    for cell in cells:
                        if cell and cell not in text_mapping:
                            text_mapping[cell] = len(texts_to_translate)
                            texts_to_translate.append(cell)
            elif element_type == 'text' and line_content.strip():
                text_to_translate = line_content.strip()

            if text_to_translate and text_to_translate not in text_mapping:
                text_mapping[text_to_translate] = len(texts_to_translate)
                texts_to_translate.append(text_to_translate)

        if progress:
            progress(0.6, desc=f"批量翻译文本... (共{len(texts_to_translate)}段)")

        # 批量翻译所有文本
        translated_texts = {}
        if texts_to_translate:
            logger.info(f"开始翻译 {len(texts_to_translate)} 段文本")

            # 使用逐个翻译的方式，更稳定可靠
            for i, text in enumerate(texts_to_translate):
                if progress and i % 5 == 0:
                    progress_value = 0.6 + (i / len(texts_to_translate)) * 0.2
                    progress(progress_value, desc=f"翻译中... ({i+1}/{len(texts_to_translate)})")

                # 在线程池中执行同步翻译函数，避免阻塞事件循环
                import concurrent.futures
                import asyncio

                loop = asyncio.get_event_loop()
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    translated_text = await loop.run_in_executor(executor, translator_func, text)

                translated_texts[text] = translated_text
                logger.debug(f"翻译完成 {i+1}/{len(texts_to_translate)}: '{text[:30]}...' -> '{translated_text[:30]}...'")

                # 添加小延迟避免请求过快
                await asyncio.sleep(0.1)

        if progress:
            progress(0.8, desc="重构Markdown文档...")

        # 第二遍：重构文档
        in_code_block = False
        for element_type, line_content, line_num in elements:
            if element_type == 'code_fence':
                in_code_block = not in_code_block
                translated_lines.append(line_content)
            elif in_code_block:
                translated_lines.append(line_content)
            elif element_type in ['empty', 'link_def']:
                translated_lines.append(line_content)
            elif element_type == 'header':
                match = re.match(r'^(#{1,6}\s+)(.+)', line_content)
                if match:
                    prefix, title_text = match.groups()
                    translated_title = translated_texts.get(title_text, title_text)
                    translated_lines.append(prefix + translated_title)
                else:
                    translated_lines.append(line_content)
            elif element_type == 'list_item':
                match = re.match(r'^(\s*[-*+]\s+|[\s]*\d+\.\s+)(.+)', line_content)
                if match:
                    prefix, item_text = match.groups()
                    translated_item = translated_texts.get(item_text, item_text)
                    translated_lines.append(prefix + translated_item)
                else:
                    translated_lines.append(line_content)
            elif element_type == 'quote':
                match = re.match(r'^(>\s*)(.+)', line_content)
                if match:
                    prefix, quote_text = match.groups()
                    translated_quote = translated_texts.get(quote_text, quote_text)
                    translated_lines.append(prefix + translated_quote)
                else:
                    translated_lines.append(line_content)
            elif element_type == 'table_row':
                if not re.match(r'^[\s|:-]+$', line_content):
                    cells = line_content.split('|')
                    translated_cells = []
                    for cell in cells:
                        if cell.strip():
                            translated_cell = translated_texts.get(cell.strip(), cell.strip())
                            translated_cells.append(cell.replace(cell.strip(), translated_cell))
                        else:
                            translated_cells.append(cell)
                    translated_lines.append('|'.join(translated_cells))
                else:
                    translated_lines.append(line_content)
            elif element_type == 'text':
                if line_content.strip():
                    translated_text = translated_texts.get(line_content.strip(), line_content)
                    translated_lines.append(translated_text)
                else:
                    translated_lines.append(line_content)
            else:
                translated_lines.append(line_content)

        if progress:
            progress(0.9, desc="完成翻译，生成结果...")

        result = '\n'.join(translated_lines)
        logger.info(f"翻译完成，结果长度: {len(result)} 字符")

        if progress:
            progress(1.0, desc="Markdown翻译完成!")

        return result

    except Exception as e:
        logger.error(f"Markdown翻译失败: {e}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        # 直接抛出异常，不降级
        raise

if __name__ == "__main__":
    # 测试代码
    test_content = """# 标题
这是一段普通文本。

## 二级标题
- 列表项1
- 列表项2

```python
# 这是代码块，不应该被翻译
def hello():
    print("Hello World")
```

> 这是引用文本

| 表格标题1 | 表格标题2 |
|----------|----------|
| 内容1     | 内容2     |
"""
    
    # 创建临时文件进行测试
    from tempfile import NamedTemporaryFile
    with NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(test_content)
        temp_path = Path(f.name)
    
    # 测试翻译
    async def test():
        # 这里需要提供真实的settings对象进行测试
        print("需要提供settings对象进行测试")
        # result = await translate_markdown_file(temp_path, settings)
        # print(result)
        # 清理临时文件
        temp_path.unlink()
    
    asyncio.run(test())