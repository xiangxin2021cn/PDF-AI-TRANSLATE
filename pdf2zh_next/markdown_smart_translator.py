#!/usr/bin/env python3
"""
智能Markdown翻译器
专门为Markdown文件设计的翻译系统，支持：
1. 基于Markdown结构的智能分块
2. Token限制感知的分块策略
3. 格式保持和预览功能
"""

import asyncio
import logging
import re
from pathlib import Path
from typing import List, Tuple, Dict, Optional, Callable

from pdf2zh_next.mineru_markdown_units import (
    hash_text,
    protect_markdown_fragments,
    restore_markdown_fragments,
    should_translate_text,
)


TABLE_SEPARATOR_PATTERN = re.compile(r'^\s*\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?\s*$')

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False

logger = logging.getLogger(__name__)

class MarkdownBlock:
    """Markdown块对象"""
    def __init__(self, content: str, block_type: str, line_start: int, line_end: int):
        self.content = content
        self.block_type = block_type  # 'header', 'paragraph', 'code', 'list', 'table', 'quote'
        self.line_start = line_start
        self.line_end = line_end
        self.translated_content: Optional[str] = None
        self.needs_translation = self._check_needs_translation()
    
    def _check_needs_translation(self) -> bool:
        """检查是否需要翻译"""
        # 代码块不需要翻译
        if self.block_type == 'code':
            return False
        # 空内容不需要翻译
        if not self.content.strip():
            return False
        # 只包含标点符号和数字的不需要翻译
        if not should_translate_text(self.content):
            return False
        return True
    
    def get_translatable_text(self) -> str:
        """提取需要翻译的文本"""
        if not self.needs_translation:
            return ""
        
        # 根据块类型提取文本
        if self.block_type == 'header':
            # 提取标题文本（去掉#号）
            match = re.match(r'^(#{1,6}\s*)(.*)', self.content)
            if match:
                return match.group(2).strip()
        elif self.block_type == 'list':
            # 提取列表项文本
            lines = []
            for line in self.content.split('\n'):
                # 匹配有序和无序列表
                match = re.match(r'^(\s*[-*+]\s*|\s*\d+\.\s*)(.*)', line)
                if match:
                    lines.append(match.group(2).strip())
            return '\n'.join(lines)
        elif self.block_type == 'quote':
            # 提取引用文本
            lines = []
            for line in self.content.split('\n'):
                match = re.match(r'^>\s*(.*)', line)
                if match:
                    lines.append(match.group(1).strip())
            return '\n'.join(lines)
        elif self.block_type == 'table':
            # 提取表格文本（跳过分隔行）
            lines = []
            for line in self.content.split('\n'):
                if not TABLE_SEPARATOR_PATTERN.match(line):
                    # 提取表格单元格
                    cells = [cell.strip() for cell in line.split('|') if cell.strip()]
                    lines.extend(cells)
            return '\n'.join(lines)
        else:
            # 普通段落
            return self.content.strip()
        
        return self.content.strip()
    
    def apply_translation(self, translated_text: str) -> str:
        """应用翻译结果到原始格式"""
        if not self.needs_translation:
            return self.content
        
        if self.block_type == 'header':
            # 保持标题格式
            match = re.match(r'^(#{1,6}\s*)(.*)', self.content)
            if match:
                return match.group(1) + translated_text
        elif self.block_type == 'list':
            # 保持列表格式
            original_lines = self.content.split('\n')
            translated_lines = translated_text.split('\n')
            result_lines = []
            
            # Ensure translated_lines has the same length as original_lines that need translation
            original_list_items = [re.match(r'^(\s*[-*+]\s*|\s*\d+\.\s*)(.*)', line) for line in original_lines]
            num_items_to_translate = sum(1 for item in original_list_items if item)

            if len(translated_lines) < num_items_to_translate:
                translated_lines.extend([''] * (num_items_to_translate - len(translated_lines)))

            trans_idx = 0
            for i, original_line in enumerate(original_lines):
                match = original_list_items[i]
                if match and trans_idx < len(translated_lines):
                    result_lines.append(match.group(1) + translated_lines[trans_idx])
                    trans_idx += 1
                else:
                    result_lines.append(original_line)
            return '\n'.join(result_lines)
        elif self.block_type == 'quote':
            # 保持引用格式
            original_lines = self.content.split('\n')
            translated_lines = translated_text.split('\n')
            result_lines = []

            if len(translated_lines) < len(original_lines):
                translated_lines.extend([''] * (len(original_lines) - len(translated_lines)))
            
            for i, original_line in enumerate(original_lines):
                match = re.match(r'^(>\s*)(.*)', original_line)
                if match and i < len(translated_lines):
                    result_lines.append(match.group(1) + translated_lines[i])
                else:
                    result_lines.append(original_line)
            return '\n'.join(result_lines)
        elif self.block_type == 'table':
            # 逐个单元格翻译表格
            original_lines = self.content.split('\n')
            translated_text_parts = translated_text.split('\n')
            part_idx = 0
            result_lines = []
            for line in original_lines:
                if TABLE_SEPARATOR_PATTERN.match(line): # Skip separator line
                    result_lines.append(line)
                    continue
                
                cells = line.split('|')
                translated_cells = []
                for cell in cells:
                    cell_content = cell.strip()
                    if cell_content and part_idx < len(translated_text_parts):
                        # Replace the original content with the translated part
                        translated_cells.append(cell.replace(cell_content, translated_text_parts[part_idx]))
                        part_idx += 1
                    else:
                        translated_cells.append(cell)
                result_lines.append('|'.join(translated_cells))
            return '\n'.join(result_lines)
        else:
            # 普通段落直接替换
            return translated_text
        
        return translated_text

class MarkdownParser:
    """Markdown解析器"""
    
    @staticmethod
    def parse_blocks(content: str) -> List[MarkdownBlock]:
        """解析Markdown内容为块"""
        lines = content.split('\n')
        blocks = []
        current_block_lines = []
        current_block_type = 'paragraph'
        current_line_start = 0
        in_code_block = False
        code_fence_pattern = None
        
        def finish_current_block():
            """完成当前块"""
            if current_block_lines:
                block_content = '\n'.join(current_block_lines)
                blocks.append(MarkdownBlock(
                    content=block_content,
                    block_type=current_block_type,
                    line_start=current_line_start,
                    line_end=current_line_start + len(current_block_lines) - 1
                ))
                current_block_lines.clear()
        
        for i, line in enumerate(lines):
            # 检查代码块
            if re.match(r'^```', line) or re.match(r'^~~~', line):
                if not in_code_block:
                    # 开始代码块
                    finish_current_block()
                    in_code_block = True
                    code_fence_pattern = line[:3]
                    current_block_type = 'code'
                    current_line_start = i
                    current_block_lines = [line]
                elif line.startswith(code_fence_pattern):
                    # 结束代码块
                    current_block_lines.append(line)
                    finish_current_block()
                    in_code_block = False
                    current_block_type = 'paragraph'
                    current_line_start = i + 1
                else:
                    current_block_lines.append(line)
                continue
            
            if in_code_block:
                current_block_lines.append(line)
                continue
            
            # 检查标题
            if re.match(r'^#{1,6}\s', line):
                finish_current_block()
                current_block_type = 'header'
                current_line_start = i
                current_block_lines = [line]
                finish_current_block()
                current_block_type = 'paragraph'
                current_line_start = i + 1
                continue
            
            # 检查列表
            if re.match(r'^\s*[-*+]\s', line) or re.match(r'^\s*\d+\.\s', line):
                if current_block_type != 'list':
                    finish_current_block()
                    current_block_type = 'list'
                    current_line_start = i
                current_block_lines.append(line)
                continue
            
            # 检查引用
            if re.match(r'^>\s*', line):
                if current_block_type != 'quote':
                    finish_current_block()
                    current_block_type = 'quote'
                    current_line_start = i
                current_block_lines.append(line)
                continue
            
            # 检查表格
            if '|' in line and line.strip():
                if current_block_type != 'table':
                    finish_current_block()
                    current_block_type = 'table'
                    current_line_start = i
                current_block_lines.append(line)
                continue
            
            # 空行处理
            if not line.strip():
                if current_block_lines:
                    finish_current_block()
                    current_block_type = 'paragraph'
                    current_line_start = i + 1
                continue
            
            # 普通段落
            if current_block_type not in ['paragraph']:
                finish_current_block()
                current_block_type = 'paragraph'
                current_line_start = i
            current_block_lines.append(line)
        
        # 处理最后一个块
        finish_current_block()
        
        return blocks

class SmartMarkdownTranslator:
    """智能Markdown翻译器"""
    
    def __init__(self, max_tokens: int = 3000):
        self.max_tokens = max_tokens
        if HAS_TIKTOKEN:
            self.encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4的编码
        else:
            self.encoding = None
    
    def count_tokens(self, text: str) -> int:
        """计算文本的token数量"""
        if self.encoding:
            return len(self.encoding.encode(text))
        else:
            cjk_count = sum(1 for char in text if '\u4e00' <= char <= '\u9fff')
            other_count = len(text) - cjk_count
            return max(1, int(cjk_count * 1.5 + other_count * 0.25))

    def _split_oversized_block(self, block: MarkdownBlock) -> List[MarkdownBlock]:
        """Splits an oversized block into smaller blocks based on sentence boundaries."""
        logger.info(f"Splitting oversized {block.block_type} block (lines {block.line_start}-{block.line_end}).")
        text = block.get_translatable_text()
        # Split text by sentences. This is a simple regex and might not be perfect for all cases.
        sentences = re.split(r'(?<=[.?!])\s+', text)
        
        new_blocks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            current_chunk_tokens = self.count_tokens(current_chunk)

            if current_chunk_tokens + sentence_tokens > self.max_tokens:
                if current_chunk:
                    new_blocks.append(MarkdownBlock(
                        content=current_chunk,
                        block_type='paragraph', # Treat split parts as simple paragraphs
                        line_start=block.line_start,
                        line_end=block.line_end
                    ))
                current_chunk = sentence
            else:
                current_chunk += (" " + sentence) if current_chunk else sentence

        if current_chunk:
            new_blocks.append(MarkdownBlock(
                content=current_chunk,
                block_type='paragraph',
                line_start=block.line_start,
                line_end=block.line_end
            ))
        
        logger.info(f"Split oversized block into {len(new_blocks)} smaller blocks.")
        return new_blocks

    def group_blocks_by_tokens(self, blocks: List[MarkdownBlock]) -> List[List[MarkdownBlock]]:
        """根据token限制将块分组, 并拆分超大块."""
        
        # First pass: split any oversized blocks
        processed_blocks = []
        for block in blocks:
            if not block.needs_translation:
                processed_blocks.append(block)
                continue

            block_tokens = self.count_tokens(block.get_translatable_text())
            if block_tokens > self.max_tokens:
                processed_blocks.extend(self._split_oversized_block(block))
            else:
                processed_blocks.append(block)

        # Second pass: group the processed blocks
        groups = []
        current_group = []
        current_tokens = 0
        
        for block in processed_blocks:
            if not block.needs_translation:
                if current_group:
                    groups.append(current_group)
                groups.append([block])
                current_group = []
                current_tokens = 0
                continue
            
            text = block.get_translatable_text()
            block_tokens = self.count_tokens(text)
            
            if current_tokens + block_tokens > self.max_tokens and current_group:
                groups.append(current_group)
                current_group = [block]
                current_tokens = block_tokens
            else:
                current_group.append(block)
                current_tokens += block_tokens
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    async def translate_group(self, blocks: List[MarkdownBlock], translator_func: Callable, progress_callback: Optional[Callable] = None) -> None:
        """翻译一组块"""
        # 收集需要翻译的文本
        texts_to_translate = []
        translatable_blocks = []

        for block in blocks:
            if block.needs_translation:
                text = block.get_translatable_text()
                if text:
                    texts_to_translate.append(text)
                    translatable_blocks.append(block)

        if not texts_to_translate:
            return

        # 批量翻译
        if len(texts_to_translate) == 1:
            # 单个文本直接翻译
            try:
                translated = await self._translate_text(translator_func, texts_to_translate[0])
                translatable_blocks[0].translated_content = translatable_blocks[0].apply_translation(translated)
            except Exception as e:
                logger.warning(f"单个文本翻译失败: {e}")
                # 翻译失败时保持原文
                translatable_blocks[0].translated_content = translatable_blocks[0].content
        else:
            # 多个文本合并翻译
            separator_token = f"ZXQBLOCKSEPARATOR{hash_text(''.join(texts_to_translate)).upper()}ZXQ"
            separator = f"\n{separator_token}\n"
            combined_text = separator.join(texts_to_translate)
            try:
                translated_combined = await self._translate_text(translator_func, combined_text)

                # 分割翻译结果
                translated_parts = re.split(rf"\s*{re.escape(separator_token)}\s*", translated_combined)

                # 如果分割结果数量匹配，应用翻译
                if len(translated_parts) == len(translatable_blocks):
                    for block, translated in zip(translatable_blocks, translated_parts):
                        block.translated_content = block.apply_translation(translated.strip())
                else:
                    # 分割失败，逐个翻译
                    logger.warning("批量翻译分割失败，改为逐个翻译")
                    await self._translate_individually(translatable_blocks, translator_func)
            except Exception as e:
                logger.warning(f"批量翻译失败: {e}，改为逐个翻译")
                await self._translate_individually(translatable_blocks, translator_func)

    async def _translate_individually(self, blocks: List[MarkdownBlock], translator_func: Callable) -> None:
        """逐个翻译块"""
        for block in blocks:
            try:
                text = block.get_translatable_text()
                translated = await self._translate_text(translator_func, text)
                block.translated_content = block.apply_translation(translated)
            except Exception as e:
                logger.warning(f"单个块翻译失败: {e}，保持原文")
                # 翻译失败时保持原文
                block.translated_content = block.content
    
    async def _translate_text(self, translator_func: Callable, text: str) -> str:
        """使用 asyncio.to_thread 安全地调用同步的翻译函数"""
        if not text.strip():
            return ""
            
        logger.debug(f"准备翻译文本 (前100字符): '{text[:100]}...'" )
        try:
            protected_text, protections = protect_markdown_fragments(text)
            # asyncio.to_thread 是在异步代码中运行同步函数的推荐方式
            translated_text = await asyncio.wait_for(
                asyncio.to_thread(translator_func, protected_text),
                timeout=60.0  # 设置60秒超时
            )
            translated_text = restore_markdown_fragments(translated_text, protections)
            logger.debug(f"翻译成功 (前100字符): '{translated_text[:100]}...'" )
            return translated_text
        except asyncio.TimeoutError:
            logger.error(f"翻译超时 (前100字符): '{text[:100]}...'" )
            return f"[翻译超时] {text}"
        except Exception as e:
            logger.error(f"翻译过程中出现错误: {e}", exc_info=True)
            logger.error(f"出错的文本 (前100字符): '{text[:100]}...'" )
            return f"[翻译错误] {text}"
    
    async def translate_markdown(self, content: str, translator_func: Callable, progress_callback: Optional[Callable] = None) -> str:
        """翻译整个Markdown文档"""
        logger.info("开始智能Markdown翻译")
        
        # 解析Markdown块
        blocks = MarkdownParser.parse_blocks(content)
        logger.info(f"解析得到 {len(blocks)} 个Markdown块")
        
        # 按token限制分组
        groups = self.group_blocks_by_tokens(blocks)
        logger.info(f"分为 {len(groups)} 个翻译组")
        
        all_blocks = [block for group in groups for block in group]

        # 翻译每个组
        for i, group in enumerate(groups):
            if progress_callback:
                progress = (i + 1) / len(groups)
                progress_callback(progress, f"翻译第 {i+1}/{len(groups)} 组...")
            
            # Skip groups that contain only non-translatable blocks
            if any(b.needs_translation for b in group):
                await self.translate_group(group, translator_func, progress_callback)
            
            # 添加延迟避免请求过快
            await asyncio.sleep(0.1)
        
        # 重构文档
        result_lines = []
        for block in all_blocks:
            if block.translated_content is not None:
                result_lines.append(block.translated_content)
            else:
                result_lines.append(block.content)
        
        result = '\n'.join(result_lines)
        logger.info(f"翻译完成，结果长度: {len(result)} 字符")
        
        return result

async def translate_markdown_smart(file_path: Path, settings, progress=None) -> str:
    """
    智能翻译Markdown文件的主函数
    
    Args:
        file_path: Markdown文件路径
        settings: 翻译设置
        progress: 进度回调函数
        
    Returns:
        翻译后的Markdown内容
    """
    try:
        logger.info(f"开始智能翻译Markdown文件: {file_path}")
        
        if progress:
            progress(0.1, desc="读取Markdown文件...")
        
        # 读取文件内容
        content = file_path.read_text(encoding='utf-8')
        logger.info(f"文件读取成功，内容长度: {len(content)} 字符")
        
        if progress:
            progress(0.2, desc="初始化翻译器...")
        
        # 获取翻译函数
        from pdf2zh_next.translator.utils import get_translator
        translator = get_translator(settings)
        logger.info(f"翻译器初始化成功: {type(translator).__name__}")
        
        def translator_func(text: str) -> str:
            # 使用与PDF翻译相同的方法
            logger.critical(f"TRANSLATING MARKDOWN BLOCK: >>>{text}<<<")
            return translator.translate(text)
        
        if progress:
            progress(0.3, desc="解析Markdown结构...")
        
        # 创建智能翻译器
        smart_translator = SmartMarkdownTranslator(max_tokens=3000)
        
        # 执行翻译
        result = await smart_translator.translate_markdown(
            content, 
            translator_func, 
            progress_callback=lambda p, desc: progress(0.3 + p * 0.6, desc) if progress else None
        )
        
        if progress:
            progress(1.0, desc="Markdown翻译完成!")
        
        return result
        
    except Exception as e:
        logger.error(f"智能Markdown翻译失败: {e}")
        import traceback
        logger.error(f"详细错误信息: {traceback.format_exc()}")
        raise
