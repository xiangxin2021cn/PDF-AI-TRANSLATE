# PDFMathTranslate-next 双方案实施计划

## 📋 项目目标

基于调研结果,实现以下核心目标:

1. **双路径PDF处理架构**
   - 路径1: BabelDOC (保持原PDF格式)
   - 路径2: MinerU (结构化输出)

2. **多样化输出格式**
   - PDF (单语/双语)
   - Markdown
   - HTML
   - JSON (结构化数据)

3. **现代化UI改造**
   - 参考 reference-them 的设计风格
   - 提升用户体验
   - 增加交互式功能

---

## 🎯 实施阶段

### 阶段1: 核心架构重构 (第1-2周)

#### 1.1 MinerU集成模块

**文件**: `pdf2zh_next/mineru_pipeline.py`

**功能**:
- PDF → MinerU → Blocks提取
- 智能翻译处理
- 多格式输出

**关键类**:
```python
class MinerUTranslationPipeline:
    - extract_structure()  # 提取文档结构
    - translate_blocks()   # 翻译内容块
    - format_output()      # 格式化输出
```

#### 1.2 输出管理器

**文件**: `pdf2zh_next/output_manager.py`

**功能**:
- 统一输出接口
- 支持多种格式
- 文件保存管理

#### 1.3 配置扩展

**修改文件**: `pdf2zh_next/config/model.py`

**新增配置**:
```python
class PDFSettings:
    output_format: str = 'pdf'  # pdf, markdown, html, json
    
class MinerUSettings:
    backend: str = 'transformers'
    model_name: str = 'opendatalab/MinerU2.5-2509-1.2B'
    server_url: Optional[str] = None
    dpi: int = 260
```

#### 1.4 高层API修改

**修改文件**: `pdf2zh_next/high_level.py`

**新增函数**:
```python
async def _translate_with_mineru(settings, file):
    """使用MinerU路径翻译"""
    
async def _translate_with_babeldoc(settings, file):
    """使用BabelDOC路径翻译"""
```

**修改函数**:
```python
async def do_translate_async_stream(settings, file):
    # 根据output_format选择路径
    if settings.pdf.output_format == 'pdf':
        async for event in _translate_with_babeldoc(settings, file):
            yield event
    else:
        async for event in _translate_with_mineru(settings, file):
            yield event
```

---

### 阶段2: UI现代化改造 (第2-3周)

#### 2.1 设计风格参考

**参考**: `reference-them/index.html`

**核心设计元素**:
- 🎨 配色方案: 温暖的橙色系 + 简约白色
- 📐 布局: 响应式网格布局
- ✨ 动画: 平滑过渡和淡入效果
- 🎯 交互: 卡片式设计,悬停效果

#### 2.2 新UI组件设计

**主页Hero区域**:
```python
with gr.Blocks(theme=gr.themes.Soft()) as demo:
    # Hero Section
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("""
            # 🚀 PDFMathTranslate-next
            ## 革命性的PDF科学文献翻译工具
            
            保持公式、图表、表格完整性的同时,提供多种输出格式
            """)
            
        with gr.Column(scale=1):
            gr.Image("assets/hero_image.png")
```

**功能卡片区域**:
```python
with gr.Row():
    with gr.Column():
        gr.Markdown("### 📄 PDF格式保持")
        gr.Markdown("精确保持原始布局和格式")
        
    with gr.Column():
        gr.Markdown("### 📝 Markdown输出")
        gr.Markdown("结构化文档,易于编辑")
        
    with gr.Column():
        gr.Markdown("### 🌐 HTML网页")
        gr.Markdown("直接在浏览器查看")
```

#### 2.3 交互式输出格式选择

**设计**:
```python
with gr.Tab("翻译设置"):
    output_format = gr.Radio(
        choices=[
            ("📄 PDF格式 (保持原格式)", "pdf"),
            ("📝 Markdown (结构化文档)", "markdown"),
            ("🌐 HTML (网页格式)", "html"),
            ("📊 JSON (数据格式)", "json")
        ],
        value="pdf",
        label="输出格式",
        info="选择翻译后的输出格式"
    )
    
    # 根据选择显示不同的说明
    format_description = gr.Markdown()
    
    def update_description(format_type):
        descriptions = {
            "pdf": "✅ 保持原PDF布局\n✅ 支持单语/双语\n✅ 适合学术论文",
            "markdown": "✅ 易于编辑\n✅ 版本控制友好\n✅ 适合技术文档",
            "html": "✅ 浏览器直接查看\n✅ 支持CSS样式\n✅ 适合在线发布",
            "json": "✅ 结构化数据\n✅ 便于程序处理\n✅ 适合数据分析"
        }
        return descriptions.get(format_type, "")
    
    output_format.change(
        update_description,
        inputs=[output_format],
        outputs=[format_description]
    )
```

#### 2.4 实时预览功能

**Markdown预览**:
```python
with gr.Tab("预览"):
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### 原文")
            original_preview = gr.Markdown()
            
        with gr.Column(scale=1):
            gr.Markdown("### 译文")
            translated_preview = gr.Markdown()
```

**HTML预览**:
```python
with gr.Tab("HTML预览"):
    html_preview = gr.HTML()
```

#### 2.5 进度可视化

**参考**: `reference-them/index.html` 的进度条设计

```python
def create_progress_display():
    with gr.Column():
        progress_bar = gr.Progress()
        status_text = gr.Markdown("准备就绪...")
        
        # 阶段指示器
        with gr.Row():
            stage_extract = gr.Markdown("⏳ 提取文档")
            stage_translate = gr.Markdown("⏳ 翻译内容")
            stage_format = gr.Markdown("⏳ 格式化输出")
            
    return progress_bar, status_text, [stage_extract, stage_translate, stage_format]
```

---

### 阶段3: 功能增强 (第3-4周)

#### 3.1 表格翻译优化

**文件**: `pdf2zh_next/mineru_pipeline.py`

**功能**:
```python
def translate_table_advanced(self, table_html):
    """高级表格翻译
    
    功能:
    - 识别表头和数据行
    - 保持合并单元格
    - 智能翻译单元格内容
    """
    import pandas as pd
    from bs4 import BeautifulSoup
    
    # 解析表格
    soup = BeautifulSoup(table_html, 'html.parser')
    table = soup.find('table')
    
    # 提取表头
    headers = []
    for th in table.find_all('th'):
        text = th.get_text(strip=True)
        translated = self.translator.translate(text) if text else ''
        headers.append(translated)
    
    # 提取数据行
    rows = []
    for tr in table.find_all('tr')[1:]:  # 跳过表头
        row = []
        for td in tr.find_all('td'):
            text = td.get_text(strip=True)
            # 判断是否需要翻译(数字、公式不翻译)
            if self._should_translate_cell(text):
                translated = self.translator.translate(text)
            else:
                translated = text
            row.append(translated)
        rows.append(row)
    
    # 重建表格
    return self._rebuild_table(headers, rows)
```

#### 3.2 公式处理

**LaTeX公式保持**:
```python
def process_formula(self, formula_block):
    """处理公式块
    
    功能:
    - 识别LaTeX公式
    - 在Markdown中正确格式化
    - 保持公式不翻译
    """
    latex_content = formula_block.get('content', '')
    
    # 判断是行内还是块级公式
    if formula_block.get('inline', False):
        return f"${latex_content}$"
    else:
        return f"$$\n{latex_content}\n$$"
```

#### 3.3 图表处理

**图表说明翻译**:
```python
def process_figure(self, figure_block):
    """处理图表块
    
    功能:
    - 提取图表图像
    - 翻译图表说明
    - 生成Markdown/HTML
    """
    # 保存图像
    image_data = figure_block.get('image')
    image_path = self._save_image(image_data)
    
    # 翻译说明
    caption = figure_block.get('caption', '')
    translated_caption = self.translator.translate(caption) if caption else ''
    
    # 生成Markdown
    if self.output_format == 'markdown':
        return f"![{translated_caption}]({image_path})\n\n*{translated_caption}*"
    elif self.output_format == 'html':
        return f'<figure><img src="{image_path}" alt="{translated_caption}"><figcaption>{translated_caption}</figcaption></figure>'
```

#### 3.4 批量处理

**文件**: `pdf2zh_next/batch_processor.py`

```python
class BatchProcessor:
    """批量处理多个PDF文件"""
    
    def __init__(self, settings):
        self.settings = settings
        
    async def process_directory(self, directory_path, output_dir):
        """处理目录中的所有PDF文件"""
        pdf_files = list(Path(directory_path).glob("*.pdf"))
        
        results = []
        for i, pdf_file in enumerate(pdf_files):
            logger.info(f"处理 {i+1}/{len(pdf_files)}: {pdf_file.name}")
            
            try:
                result = await do_translate_async_stream(
                    self.settings,
                    pdf_file
                )
                results.append({
                    'file': pdf_file.name,
                    'status': 'success',
                    'result': result
                })
            except Exception as e:
                results.append({
                    'file': pdf_file.name,
                    'status': 'error',
                    'error': str(e)
                })
        
        return results
```

---

### 阶段4: 测试和优化 (第4-5周)

#### 4.1 单元测试

**文件**: `tests/test_mineru_pipeline.py`

```python
import pytest
from pdf2zh_next.mineru_pipeline import MinerUTranslationPipeline

def test_extract_structure():
    """测试文档结构提取"""
    pipeline = MinerUTranslationPipeline(settings)
    result = pipeline.extract_structure("test.pdf")
    assert 'blocks' in result
    
def test_translate_blocks():
    """测试内容翻译"""
    pipeline = MinerUTranslationPipeline(settings)
    blocks = [{'type': 'text', 'content': 'Hello'}]
    translated = pipeline.translate_blocks(blocks)
    assert translated[0]['content'] != 'Hello'
    
def test_format_markdown():
    """测试Markdown格式化"""
    pipeline = MinerUTranslationPipeline(settings)
    blocks = [{'type': 'text', 'content': '你好'}]
    markdown = pipeline._to_markdown(blocks)
    assert '你好' in markdown
```

#### 4.2 集成测试

**测试场景**:
1. 学术论文翻译 (PDF → PDF)
2. 技术文档翻译 (PDF → Markdown)
3. 知识库构建 (PDF → HTML)
4. 数据提取 (PDF → JSON)

#### 4.3 性能优化

**缓存策略**:
```python
class TranslationCache:
    """统一翻译缓存"""
    
    def __init__(self, cache_dir=".cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        
    def get(self, text, lang_pair):
        """获取缓存的翻译"""
        cache_key = self._make_key(text, lang_pair)
        cache_file = self.cache_dir / f"{cache_key}.txt"
        
        if cache_file.exists():
            return cache_file.read_text(encoding='utf-8')
        return None
        
    def set(self, text, translation, lang_pair):
        """设置翻译缓存"""
        cache_key = self._make_key(text, lang_pair)
        cache_file = self.cache_dir / f"{cache_key}.txt"
        cache_file.write_text(translation, encoding='utf-8')
```

**并行处理**:
```python
async def translate_blocks_parallel(self, blocks, max_workers=4):
    """并行翻译多个块"""
    from concurrent.futures import ThreadPoolExecutor
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for block in blocks:
            if block['type'] == 'text':
                future = executor.submit(
                    self.translator.translate,
                    block['content']
                )
                futures.append((block, future))
        
        for block, future in futures:
            block['translated'] = future.result()
    
    return blocks
```

---

## 📊 UI改造详细设计

### 主题配置

**文件**: `pdf2zh_next/gui_theme.py`

```python
import gradio as gr

def create_custom_theme():
    """创建自定义主题"""
    return gr.themes.Soft(
        primary_hue="orange",
        secondary_hue="gray",
        neutral_hue="gray",
        font=[
            gr.themes.GoogleFont("Inter"),
            "ui-sans-serif",
            "system-ui",
        ],
        font_mono=[
            gr.themes.GoogleFont("IBM Plex Mono"),
            "ui-monospace",
        ],
    ).set(
        body_background_fill="*neutral_50",
        body_background_fill_dark="*neutral_900",
        button_primary_background_fill="*primary_500",
        button_primary_background_fill_hover="*primary_600",
        button_primary_text_color="white",
        block_title_text_weight="600",
        block_border_width="1px",
        block_shadow="*shadow_drop_lg",
        button_shadow="*shadow_drop",
        button_large_padding="12px 24px",
    )
```

### 自定义CSS

**文件**: `pdf2zh_next/assets/custom.css`

```css
/* 参考 reference-them 的设计 */

:root {
    --primary-bg: #F5F3F0;
    --secondary-bg: #FFFFFF;
    --accent-color: #C17B5A;
    --accent-light: #D4A574;
    --text-primary: #2C2C2C;
    --text-secondary: #6B7280;
}

.hero-section {
    background: linear-gradient(135deg, var(--primary-bg) 0%, #E8E2DB 100%);
    padding: 4rem 2rem;
    border-radius: 16px;
    margin-bottom: 2rem;
}

.feature-card {
    background: var(--secondary-bg);
    border: 1px solid #E5E7EB;
    border-radius: 12px;
    padding: 2rem;
    transition: all 0.3s ease;
}

.feature-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
}

.gradient-text {
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-light) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}

.progress-bar {
    height: 4px;
    background: linear-gradient(90deg, var(--accent-color) 0%, var(--accent-light) 100%);
    border-radius: 2px;
    transition: width 0.3s ease;
}

.status-indicator {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 8px;
}

.status-active { background-color: #10B981; }
.status-loading { background-color: #F59E0B; }
.status-idle { background-color: #6B7280; }
```

### 主界面布局

**修改文件**: `pdf2zh_next/gui.py`

```python
def create_main_interface():
    """创建主界面"""
    
    with gr.Blocks(
        theme=create_custom_theme(),
        css=Path("pdf2zh_next/assets/custom.css").read_text(),
        title="PDFMathTranslate-next - 科学文献翻译工具"
    ) as demo:
        
        # Hero Section
        with gr.Row(elem_classes="hero-section"):
            with gr.Column(scale=1):
                gr.Markdown("""
                # 🚀 PDFMathTranslate-next
                
                <span class="gradient-text" style="font-size: 2rem; font-weight: bold;">
                革命性的PDF科学文献翻译工具
                </span>
                
                保持公式、图表、表格完整性的同时,提供多种输出格式
                
                ✨ 支持20+种翻译引擎 | 📄 精确保持PDF格式 | 📝 多样化输出
                """)
                
                with gr.Row():
                    quick_start_btn = gr.Button(
                        "🎯 快速开始",
                        variant="primary",
                        size="lg"
                    )
                    learn_more_btn = gr.Button(
                        "📚 了解更多",
                        variant="secondary",
                        size="lg"
                    )
                    
            with gr.Column(scale=1):
                gr.Image(
                    "assets/hero_diagram.png",
                    label=None,
                    show_label=False
                )
        
        # Feature Cards
        gr.Markdown("## ✨ 核心功能")
        
        with gr.Row():
            with gr.Column(elem_classes="feature-card"):
                gr.Markdown("""
                ### 📄 PDF格式保持
                
                精确保持原始PDF的布局、字体和格式
                
                - ✅ 公式完整保留
                - ✅ 图表位置不变
                - ✅ 双语对照输出
                """)
                
            with gr.Column(elem_classes="feature-card"):
                gr.Markdown("""
                ### 📝 Markdown输出
                
                结构化文档,易于编辑和版本控制
                
                - ✅ 保持文档结构
                - ✅ LaTeX公式支持
                - ✅ 适合技术文档
                """)
                
            with gr.Column(elem_classes="feature-card"):
                gr.Markdown("""
                ### 🌐 HTML网页
                
                直接在浏览器查看,支持CSS样式
                
                - ✅ 响应式设计
                - ✅ 在线发布友好
                - ✅ 支持交互元素
                """)
        
        # Main Translation Interface
        with gr.Tabs() as tabs:
            # Tab 1: 翻译
            with gr.Tab("📄 翻译", id=0):
                create_translation_tab()
            
            # Tab 2: 批量处理
            with gr.Tab("📁 批量处理", id=1):
                create_batch_tab()
            
            # Tab 3: 设置
            with gr.Tab("⚙️ 设置", id=2):
                create_settings_tab()
            
            # Tab 4: 关于
            with gr.Tab("ℹ️ 关于", id=3):
                create_about_tab()
    
    return demo
```

---

## 📅 时间表

| 阶段 | 任务 | 时间 | 负责人 |
|------|------|------|--------|
| 1 | MinerU集成 | 第1周 | 开发团队 |
| 1 | 配置和API修改 | 第1-2周 | 开发团队 |
| 2 | UI设计和实现 | 第2-3周 | UI团队 |
| 3 | 功能增强 | 第3-4周 | 开发团队 |
| 4 | 测试和优化 | 第4-5周 | 测试团队 |
| 5 | 文档和发布 | 第5周 | 全体 |

---

## ✅ 验收标准

### 功能验收
- [ ] 支持4种输出格式(PDF/Markdown/HTML/JSON)
- [ ] PDF格式保持准确率 > 95%
- [ ] Markdown输出质量可用
- [ ] 表格翻译准确率 > 90%
- [ ] 公式完整保留

### 性能验收
- [ ] 单页处理时间 < 30秒
- [ ] 内存占用 < 4GB
- [ ] 支持100页以上PDF

### UI验收
- [ ] 响应式设计,支持移动端
- [ ] 加载时间 < 3秒
- [ ] 交互流畅,无卡顿
- [ ] 符合现代设计规范

---

## 🚀 下一步行动

1. **立即开始**: 创建 `mineru_pipeline.py` 模块
2. **并行进行**: UI改造可以同步进行
3. **持续测试**: 每个功能完成后立即测试
4. **文档同步**: 边开发边完善文档

准备好开始实施了吗? 🎯

