# MinerU翻译流程调研报告

## 📋 调研目标

确定MinerU路径的最佳翻译流程:
- **方案A**: 先完整识别 → 生成完整MD → 整体翻译
- **方案B**: 边识别边翻译 (流式处理)

## 🔍 原应用翻译引擎分析

### 翻译引擎架构

**核心接口**: `BaseTranslator`
- 位置: `pdf2zh_next/translator/base_translator.py`
- 创建方法: `get_translator(settings)` from `pdf2zh_next/translator/utils.py`

**关键方法**:
```python
class BaseTranslator:
    def translate(self, text, ignore_cache=False, rate_limit_params=None):
        """主翻译方法
        
        功能:
        1. 检查缓存
        2. 速率限制
        3. 调用do_translate()
        4. 保存缓存
        """
        
    def do_translate(self, text, rate_limit_params=None):
        """实际翻译实现 (子类重写)"""
```

**支持的翻译引擎** (20+种):
- OpenAI, Azure OpenAI
- Google Translate, DeepL
- SiliconFlow, Ollama
- Xinference, Qwen MT
- 等等...

**使用示例**:
```python
from pdf2zh_next.translator import get_translator

# 创建翻译器
translator = get_translator(settings)

# 翻译文本
translated = translator.translate("Hello world")
```

### 翻译特性

1. **自动缓存**: 避免重复翻译
2. **速率限制**: QPS控制
3. **批量翻译**: 支持多段文本
4. **公式保护**: 使用占位符保护LaTeX公式
5. **富文本支持**: 保持格式标记

---

## 📊 两种方案对比分析

### 方案A: 先识别后翻译 (推荐 ⭐⭐⭐⭐⭐)

#### 流程图

```
PDF文件
  ↓
MinerU完整识别 (所有页面)
  ↓
生成结构化数据
  {
    pages: [
      {blocks: [text, formula, table, figure]},
      {blocks: [...]},
      ...
    ]
  }
  ↓
提取需要翻译的文本块
  [
    "This is paragraph 1",
    "This is paragraph 2",
    "Table cell content",
    ...
  ]
  ↓
批量翻译 (使用原应用翻译引擎)
  ↓
将翻译结果填回结构化数据
  ↓
生成输出文件
  ├─ translated.md
  ├─ dual.md
  ├─ translated.html
  └─ dual.html
```

#### 优点

✅ **简单清晰**
- 流程线性,易于理解和维护
- 识别和翻译完全解耦
- 调试方便

✅ **充分利用缓存**
- 所有文本块可以批量查询缓存
- 避免重复翻译相同内容
- 缓存命中率高

✅ **批量优化**
- 可以合并小文本块,减少API调用
- 更好的速率控制
- 降低翻译成本

✅ **容错性好**
- 识别失败不影响已识别内容
- 翻译失败可以重试
- 可以保存中间结果

✅ **支持预览**
- 识别完成后可以预览原文
- 用户可以选择性翻译
- 支持增量翻译

#### 缺点

⚠️ **内存占用**
- 需要在内存中保存完整结构
- 大文档可能占用较多内存
- 解决方案: 分页处理

⚠️ **等待时间**
- 需要等待完整识别完成
- 用户体验略差
- 解决方案: 显示进度条

#### 实现复杂度: ⭐⭐ (简单)

---

### 方案B: 边识别边翻译 (流式处理)

#### 流程图

```
PDF文件
  ↓
逐页处理:
  第1页 → MinerU识别 → 提取文本 → 翻译 → 生成输出
  第2页 → MinerU识别 → 提取文本 → 翻译 → 生成输出
  第3页 → MinerU识别 → 提取文本 → 翻译 → 生成输出
  ...
  ↓
合并所有页面输出
  ↓
生成最终文件
```

#### 优点

✅ **内存友好**
- 逐页处理,内存占用小
- 适合超大文档

✅ **实时反馈**
- 用户可以实时看到进度
- 更好的用户体验

✅ **早期失败检测**
- 问题可以早发现
- 及时中断处理

#### 缺点

❌ **缓存效率低**
- 无法批量查询缓存
- 跨页面的重复内容无法优化

❌ **API调用多**
- 无法合并小文本块
- 翻译成本更高
- 速率限制更复杂

❌ **实现复杂**
- 需要管理异步流
- 错误处理复杂
- 状态管理困难

❌ **难以优化**
- 无法全局优化翻译策略
- 无法智能合并文本块

#### 实现复杂度: ⭐⭐⭐⭐ (复杂)

---

## 🎯 推荐方案: 方案A (先识别后翻译)

### 理由

1. **与原应用翻译引擎完美配合**
   - 原应用的翻译引擎设计就是为批量翻译优化的
   - 缓存机制在批量场景下效果最好
   - 速率限制更容易控制

2. **MinerU的特点**
   - MinerU本身就是批量处理模型
   - 一次性识别整个文档效率更高
   - 结构化输出天然适合后处理

3. **实现简单**
   - 代码清晰,易于维护
   - 调试方便
   - 扩展性好

4. **用户体验**
   - 虽然需要等待,但可以通过进度条改善
   - 最终输出质量更高
   - 支持预览和增量翻译

---

## 💡 方案A详细设计

### 核心流程

```python
class MinerUTranslationPipeline:
    """MinerU翻译管道 - 方案A实现"""
    
    def __init__(self, settings, storage_manager):
        self.settings = settings
        self.storage = storage_manager
        
        # 使用原应用的翻译引擎
        from pdf2zh_next.translator import get_translator
        self.translator = get_translator(settings)
        
        # MinerU适配器
        self.mineru = MinerUEnhancedAdapter(
            model_path=settings.mineru.model_path,
            backend=settings.mineru.backend,
        )
    
    async def translate_pdf(self, pdf_path, project_id):
        """完整翻译流程"""
        
        # ========== 阶段1: MinerU识别 (30%) ==========
        yield {"stage": "extract", "progress": 0.0, "message": "正在识别文档结构..."}
        
        structure = self.mineru.extract_from_pdf(pdf_path)
        
        yield {"stage": "extract", "progress": 0.3, "message": f"识别完成: {structure['total_pages']} 页"}
        
        # ========== 阶段2: 提取文本块 (10%) ==========
        yield {"stage": "prepare", "progress": 0.3, "message": "正在准备翻译..."}
        
        text_blocks = self._extract_translatable_blocks(structure)
        
        yield {"stage": "prepare", "progress": 0.4, "message": f"待翻译文本块: {len(text_blocks)}"}
        
        # ========== 阶段3: 批量翻译 (50%) ==========
        yield {"stage": "translate", "progress": 0.4, "message": "正在翻译..."}
        
        translated_blocks = await self._batch_translate(text_blocks, progress_callback=lambda p: ...)
        
        yield {"stage": "translate", "progress": 0.9, "message": "翻译完成"}
        
        # ========== 阶段4: 生成输出 (10%) ==========
        yield {"stage": "format", "progress": 0.9, "message": "正在生成输出文件..."}
        
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
        
        yield {"stage": "complete", "progress": 1.0, "message": "翻译完成！"}
    
    def _extract_translatable_blocks(self, structure):
        """提取需要翻译的文本块
        
        Returns:
            [
                {
                    'id': 'page_1_block_0',
                    'type': 'text',
                    'content': 'Original text',
                    'page_num': 1,
                    'block_index': 0
                },
                ...
            ]
        """
        blocks = []
        
        for page in structure['pages']:
            page_num = page['page_num']
            
            for i, block in enumerate(page['blocks']):
                if block['type'] == 'text':
                    # 文本块需要翻译
                    blocks.append({
                        'id': f"page_{page_num}_block_{i}",
                        'type': 'text',
                        'content': block['content'],
                        'page_num': page_num,
                        'block_index': i
                    })
                    
                elif block['type'] == 'table':
                    # 表格单元格需要翻译
                    table_blocks = self._extract_table_cells(block, page_num, i)
                    blocks.extend(table_blocks)
                    
                elif block['type'] == 'figure':
                    # 图片说明需要翻译
                    if block.get('caption'):
                        blocks.append({
                            'id': f"page_{page_num}_block_{i}_caption",
                            'type': 'caption',
                            'content': block['caption'],
                            'page_num': page_num,
                            'block_index': i
                        })
                
                # formula类型不需要翻译
        
        return blocks
    
    async def _batch_translate(self, text_blocks, progress_callback=None):
        """批量翻译文本块
        
        优化策略:
        1. 合并小文本块
        2. 批量查询缓存
        3. 并发翻译
        """
        translated_blocks = {}
        total = len(text_blocks)
        
        for i, block in enumerate(text_blocks):
            # 使用原应用的翻译引擎
            translated = self.translator.translate(block['content'])
            
            translated_blocks[block['id']] = {
                'original': block['content'],
                'translated': translated,
                'type': block['type']
            }
            
            # 进度回调
            if progress_callback:
                progress = 0.4 + (i + 1) / total * 0.5
                progress_callback(progress)
        
        return translated_blocks
```

### 智能优化

#### 1. 文本块合并

```python
def _merge_small_blocks(self, blocks, max_length=500):
    """合并小文本块,减少API调用
    
    策略:
    - 同一页面的连续文本块可以合并
    - 合并后总长度不超过max_length
    - 保持块的边界信息用于后续拆分
    """
    merged = []
    current_merge = []
    current_length = 0
    
    for block in blocks:
        block_length = len(block['content'])
        
        if current_length + block_length <= max_length:
            current_merge.append(block)
            current_length += block_length
        else:
            if current_merge:
                merged.append(self._create_merged_block(current_merge))
            current_merge = [block]
            current_length = block_length
    
    if current_merge:
        merged.append(self._create_merged_block(current_merge))
    
    return merged
```

#### 2. 批量缓存查询

```python
def _batch_cache_lookup(self, blocks):
    """批量查询缓存
    
    Returns:
        cached: {block_id: translation}
        uncached: [block_id, ...]
    """
    cached = {}
    uncached = []
    
    for block in blocks:
        # 使用translator的缓存机制
        cache_result = self.translator.cache.get(block['content'])
        
        if cache_result:
            cached[block['id']] = cache_result
        else:
            uncached.append(block)
    
    return cached, uncached
```

#### 3. 并发翻译

```python
async def _concurrent_translate(self, blocks, max_workers=4):
    """并发翻译多个块"""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        loop = asyncio.get_event_loop()
        
        tasks = [
            loop.run_in_executor(
                executor,
                self.translator.translate,
                block['content']
            )
            for block in blocks
        ]
        
        results = await asyncio.gather(*tasks)
        
    return results
```

---

## 📝 实现示例

### 完整翻译流程

```python
# 1. 创建翻译管道
from pdf2zh_next.mineru_pipeline import MinerUTranslationPipeline
from pdf2zh_next.storage_manager import StorageManager

storage = StorageManager("storage")
pipeline = MinerUTranslationPipeline(settings, storage)

# 2. 创建项目
project_id = storage.create_project(
    source_pdf="paper.pdf",
    metadata={
        'title': 'Scientific Paper',
        'lang_in': 'en',
        'lang_out': 'zh',
        'translation_path': 'mineru',
        'output_formats': ['markdown', 'html']
    }
)

# 3. 执行翻译
async for event in pipeline.translate_pdf("paper.pdf", project_id):
    print(f"[{event['stage']}] {event['progress']:.0%} - {event['message']}")

# 输出:
# [extract] 0% - 正在识别文档结构...
# [extract] 30% - 识别完成: 10 页
# [prepare] 30% - 正在准备翻译...
# [prepare] 40% - 待翻译文本块: 156
# [translate] 40% - 正在翻译...
# [translate] 90% - 翻译完成
# [format] 90% - 正在生成输出文件...
# [complete] 100% - 翻译完成！
```

---

## 🎓 总结

### 最终推荐: 方案A

**核心优势**:
1. ✅ 与原应用翻译引擎完美集成
2. ✅ 实现简单,易于维护
3. ✅ 充分利用缓存,降低成本
4. ✅ 支持批量优化
5. ✅ 容错性好

**实施要点**:
1. 使用 `get_translator(settings)` 创建翻译器
2. MinerU完整识别后提取文本块
3. 批量翻译,充分利用缓存
4. 生成多种格式输出

**与原应用的区别**:
- 原应用: PDF原位翻译 (复杂,保持布局)
- MinerU路径: 结构化翻译 (简单,重新排版)

这个方案既简单又高效,完全符合您的需求! 🚀

