# PDFMathTranslate-next 改造进展报告

## 📊 当前进展 (2025-01-04)

### ✅ 已完成

#### 1. 规划文档
- [x] `docs/mineru_integration_research.md` - MinerU集成调研报告
- [x] `docs/implementation_plan.md` - 初步实施计划
- [x] `docs/detailed_implementation_plan.md` - 详细实施计划
- [x] `docs/implementation_progress.md` - 进展跟踪文档(本文档)

#### 2. 核心模块 (Track A: MinerU集成)
- [x] `pdf2zh_next/mineru_adapter.py` - MinerU适配器
  - ✅ 基础适配器 `MinerUAdapter`
  - ✅ 增强适配器 `MinerUEnhancedAdapter`
  - ✅ 统一文档结构格式
  - ✅ 支持本地transformers和HTTP两种后端

- [x] `pdf2zh_next/storage_manager.py` - 本地存储管理器
  - ✅ 项目创建和管理
  - ✅ 文件存储和检索
  - ✅ 项目索引系统
  - ✅ 元数据管理

#### 3. UI框架 (Track B: UI改造)
- [x] `pdf2zh_next/gui_theme.py` - UI主题配置
  - ✅ 自定义Gradio主题
  - ✅ 完整CSS样式(参考reference-them)
  - ✅ 响应式设计
  - ✅ 动画效果

### 🚧 进行中

#### 4. 待创建的核心文件

**高优先级**:
1. `pdf2zh_next/mineru_pipeline.py` - MinerU翻译管道
2. `pdf2zh_next/document_viewer.py` - 文档浏览器
3. `pdf2zh_next/gui_new.py` - 新UI主界面
4. `pdf2zh_next/config/model.py` - 配置扩展(添加MinerU配置)

**中优先级**:
5. `pdf2zh_next/batch_processor.py` - 批量处理器
6. `tests/test_mineru_adapter.py` - 单元测试
7. `tests/test_storage_manager.py` - 单元测试

**低优先级**:
8. `pdf2zh_next/assets/hero_bg.js` - 背景特效
9. 文档和示例

---

## 📋 下一步行动计划

### 阶段1: 完成核心功能 (本周)

#### 任务1: MinerU翻译管道
**文件**: `pdf2zh_next/mineru_pipeline.py`

**功能**:
```python
class MinerUTranslationPipeline:
    """MinerU翻译管道
    
    流程:
    1. 使用MinerUAdapter提取PDF结构
    2. 翻译各个内容块
    3. 生成多种格式输出(MD/HTML)
    4. 保存到StorageManager
    """
    
    async def translate_pdf(self, pdf_path, project_id):
        """翻译PDF并生成多格式输出"""
        
    def _to_markdown(self, structure, mode='translated'):
        """转换为Markdown格式"""
        
    def _to_html(self, structure, mode='translated'):
        """转换为HTML格式"""
```

**关键点**:
- 支持双语对照模式
- 保持公式、表格、图片的完整性
- 生成大模型友好的格式

#### 任务2: 文档浏览器
**文件**: `pdf2zh_next/document_viewer.py`

**功能**:
```python
class DocumentViewer:
    """文档浏览器 - 在Gradio中预览各种格式"""
    
    def render_file(self, project_id, file_path):
        """渲染文件内容用于Gradio显示"""
        
    def _render_pdf(self, pdf_path):
        """PDF转图片预览"""
        
    def _render_markdown(self, md_path):
        """Markdown渲染为HTML"""
        
    def _render_html(self, html_path):
        """HTML直接显示"""
```

#### 任务3: 配置扩展
**文件**: `pdf2zh_next/config/model.py`

**新增配置**:
```python
class MinerUSettings(BaseModel):
    """MinerU相关配置"""
    enabled: bool = Field(default=False, description="启用MinerU路径")
    backend: str = Field(default="transformers", description="后端类型")
    model_path: str = Field(
        default="opendatalab/MinerU2.5-2509-1.2B",
        description="模型路径"
    )
    server_url: Optional[str] = Field(default=None, description="HTTP服务器URL")
    dpi: int = Field(default=260, description="PDF渲染DPI")

class PDFSettings(BaseModel):
    """PDF处理配置"""
    # 现有配置...
    
    # 新增
    output_format: str = Field(
        default="pdf",
        description="输出格式: pdf, markdown, html, json"
    )
    translation_path: str = Field(
        default="babeldoc",
        description="翻译路径: babeldoc, mineru"
    )

class Settings(BaseModel):
    # 现有配置...
    
    # 新增
    mineru: MinerUSettings = Field(default_factory=MinerUSettings)
    storage_root: str = Field(default="storage", description="存储根目录")
```

#### 任务4: 新UI主界面
**文件**: `pdf2zh_next/gui_new.py`

**结构**:
```python
def create_main_interface():
    """创建主界面"""
    
    with gr.Blocks(theme=create_custom_theme(), css=get_custom_css()) as demo:
        # Hero Section
        create_hero_section()
        
        # Feature Cards
        create_feature_cards()
        
        # Main Tabs
        with gr.Tabs():
            with gr.Tab("📄 翻译"):
                create_translation_tab()
            
            with gr.Tab("📁 项目管理"):
                create_project_management_tab()
            
            with gr.Tab("🔍 文档浏览"):
                create_document_viewer_tab()
            
            with gr.Tab("⚙️ 设置"):
                create_settings_tab()
    
    return demo
```

---

## 🎯 关键技术点

### 1. MinerU适配

**当前状态**:
- ✅ 基础框架已完成
- ⚠️ 需要测试实际MinerU输出格式
- ⚠️ 需要完善block转换逻辑

**测试计划**:
```python
# 测试MinerU提取
from pdf2zh_next.mineru_adapter import MinerUEnhancedAdapter

adapter = MinerUEnhancedAdapter(
    model_path="C:/Users/xiang/.cache/huggingface/hub/models--opendatalab--MinerU2.5-2509-1.2B"
)

result = adapter.extract_from_pdf(
    "test/file/translate.cli.plain.text.pdf",
    pages=[1]
)

print(json.dumps(result, indent=2, ensure_ascii=False))
```

### 2. 双路径翻译流程

**BabelDOC路径** (保留):
```
PDF → BabelDOC解析 → IL中间表示 → 翻译 → PDF重组
输出: translated.pdf, dual.pdf, vocabulary.txt
```

**MinerU路径** (新增):
```
PDF → MinerU OCR → 结构化blocks → 翻译 → 格式化
输出: translated.md, dual.md, translated.html, dual.html
```

**路径选择逻辑**:
```python
if settings.pdf.output_format == 'pdf':
    # 使用BabelDOC路径
    result = await translate_with_babeldoc(pdf_path, settings)
else:
    # 使用MinerU路径
    result = await translate_with_mineru(pdf_path, settings)
```

### 3. 本地存储结构

**目录结构**:
```
storage/
├── projects/
│   ├── 20250104_143022_a1b2c3d4/
│   │   ├── source.pdf
│   │   ├── metadata.json
│   │   ├── babeldoc/
│   │   │   ├── translated.pdf
│   │   │   ├── dual.pdf
│   │   │   └── vocabulary.txt
│   │   └── mineru/
│   │       ├── translated.md
│   │       ├── dual.md
│   │       ├── translated.html
│   │       ├── dual.html
│   │       └── images/
│   │           ├── fig_1.png
│   │           └── fig_2.png
└── index.json
```

**元数据格式**:
```json
{
  "project_id": "20250104_143022_a1b2c3d4",
  "title": "Scientific Paper Title",
  "created_at": "2025-01-04T14:30:22",
  "updated_at": "2025-01-04T14:35:10",
  "status": "completed",
  "source_file": "paper.pdf",
  "source_size": 1234567,
  "lang_in": "en",
  "lang_out": "zh",
  "translation_path": "mineru",
  "output_formats": ["markdown", "html"],
  "results": {
    "mineru": [
      "translated.md",
      "dual.md",
      "translated.html",
      "dual.html"
    ]
  }
}
```

### 4. UI组件设计

**输出格式选择器**:
```python
with gr.Row():
    output_format = gr.Radio(
        choices=[
            ("📄 PDF格式 (保持原格式)", "pdf"),
            ("📝 Markdown (结构化文档)", "markdown"),
            ("🌐 HTML (网页格式)", "html"),
        ],
        value="pdf",
        label="输出格式",
        elem_classes="format-selector"
    )
```

**进度显示**:
```python
with gr.Column():
    progress = gr.Progress()
    status_text = gr.Markdown("准备就绪...")
    
    with gr.Row():
        stage_extract = gr.Markdown("⏳ 提取文档")
        stage_translate = gr.Markdown("⏳ 翻译内容")
        stage_format = gr.Markdown("⏳ 格式化输出")
```

**文档浏览器**:
```python
with gr.Row():
    # 左侧: 项目列表
    with gr.Column(scale=1):
        project_list = gr.Dataframe(
            headers=["项目", "创建时间", "状态"],
            interactive=False
        )
    
    # 右侧: 文件预览
    with gr.Column(scale=2):
        file_viewer = gr.HTML()
```

---

## 🧪 测试计划

### 单元测试

1. **MinerU适配器测试**
   - 测试PDF提取
   - 测试图片提取
   - 测试格式转换

2. **存储管理器测试**
   - 测试项目创建
   - 测试文件保存
   - 测试项目检索

3. **翻译管道测试**
   - 测试Markdown生成
   - 测试HTML生成
   - 测试双语对照

### 集成测试

1. **完整翻译流程**
   - BabelDOC路径: PDF → PDF
   - MinerU路径: PDF → Markdown
   - MinerU路径: PDF → HTML

2. **UI交互测试**
   - 文件上传
   - 格式选择
   - 进度显示
   - 结果浏览

### 性能测试

1. **处理速度**
   - 单页处理时间 < 30秒
   - 10页文档 < 5分钟

2. **内存占用**
   - 峰值内存 < 4GB
   - 支持100页以上PDF

---

## 📅 时间表

| 日期 | 任务 | 状态 |
|------|------|------|
| 2025-01-04 | 规划和基础架构 | ✅ 完成 |
| 2025-01-05 | MinerU翻译管道 | 🚧 进行中 |
| 2025-01-06 | 文档浏览器 | ⏳ 待开始 |
| 2025-01-07 | 新UI主界面 | ⏳ 待开始 |
| 2025-01-08 | 集成测试 | ⏳ 待开始 |
| 2025-01-09 | 优化和调试 | ⏳ 待开始 |
| 2025-01-10 | 文档和发布 | ⏳ 待开始 |

---

## 🎓 总结

### 已完成的工作

1. **架构设计**: 完成双路径翻译架构设计
2. **核心模块**: 实现MinerU适配器和存储管理器
3. **UI框架**: 完成主题配置和CSS样式

### 下一步重点

1. **实现翻译管道**: 连接MinerU和翻译引擎
2. **构建UI界面**: 实现用户交互界面
3. **测试验证**: 确保功能正常工作

### 技术亮点

- ✨ 双路径架构,互不干扰
- ✨ 统一的文档结构格式
- ✨ 完整的本地存储管理
- ✨ 现代化的UI设计
- ✨ 大模型友好的输出格式

准备好继续实施了! 🚀

