# PDFMathTranslate-next 详细改造计划

## 📋 需求确认

根据您的反馈，核心需求如下：

### 1. 实施策略
✅ **选择C：同时进行** - UI改造和MinerU集成并行开发

### 2. MinerU配置
- 模型路径：`C:\Users\xiang\.cache\huggingface\hub\models--opendatalab--MinerU2.5-2509-1.2B`
- 需要适配改造现有 `mineru_standalone` 代码
- 充分利用MinerU的强大OCR能力

### 3. UI设计
- ✅ 完全复制 `reference-them` 的视觉风格
- 背景特效、按钮、样式、色调保持一致
- 布局合理优化

### 4. 双路径输出策略

#### 路径1: BabelDOC (保留原有功能)
- 📄 翻译PDF稿
- 📊 对比翻译稿
- 📚 专业词汇表

#### 路径2: MinerU (新增功能)
- 📝 高保真Markdown翻译稿
- 🌐 高保真HTML翻译稿
- 📊 对比稿（MD/HTML格式）
- ❌ 不输出词汇表
- 🎯 优化为大模型友好格式

### 5. 本地存储管理系统
- 📁 统一存储所有翻译结果
- 📑 存档页面展示所有项目
- 🔍 浏览器内预览所有文件
- 📂 源文件 + 翻译文件一起管理

---

## 🏗️ 架构设计

### 整体架构图

```
用户上传PDF
    ↓
选择翻译路径
    ├─ 路径1: BabelDOC
    │   ├─ PDF解析
    │   ├─ 翻译
    │   ├─ PDF重组
    │   └─ 输出: 翻译PDF + 对比PDF + 词汇表
    │
    └─ 路径2: MinerU
        ├─ OCR识别 (MinerU)
        ├─ 结构化提取
        ├─ 翻译
        ├─ 格式化输出
        └─ 输出: MD翻译稿 + MD对比稿 + HTML翻译稿 + HTML对比稿
    ↓
本地存储管理系统
    ├─ 项目管理
    ├─ 文件存储
    └─ 浏览器预览
```

### 目录结构设计

```
PDFMathTranslate-next/
├── pdf2zh_next/
│   ├── mineru_adapter.py          # MinerU适配层 (新增)
│   ├── mineru_pipeline.py         # MinerU翻译流程 (新增)
│   ├── storage_manager.py         # 本地存储管理 (新增)
│   ├── document_viewer.py         # 文档浏览器 (新增)
│   ├── gui_new.py                 # 新UI界面 (新增)
│   ├── gui_theme.py               # UI主题配置 (新增)
│   ├── assets/
│   │   ├── custom.css             # 自定义样式 (新增)
│   │   ├── hero_bg.js             # 背景特效 (新增)
│   │   └── icons/                 # 图标资源 (新增)
│   └── ...
├── mineru_standalone/             # MinerU模块 (已有)
├── storage/                       # 本地存储目录 (新增)
│   ├── projects/                  # 项目存储
│   │   ├── {project_id}/
│   │   │   ├── source.pdf         # 源文件
│   │   │   ├── metadata.json      # 元数据
│   │   │   ├── babeldoc/          # BabelDOC输出
│   │   │   │   ├── translated.pdf
│   │   │   │   ├── dual.pdf
│   │   │   │   └── vocabulary.txt
│   │   │   └── mineru/            # MinerU输出
│   │   │       ├── translated.md
│   │   │       ├── dual.md
│   │   │       ├── translated.html
│   │   │       └── dual.html
│   └── index.json                 # 项目索引
└── reference-them/                # UI参考 (已有)
```

---

## 🚀 并行实施计划

### 第1周：基础架构搭建

#### Track A: MinerU适配 (开发团队A)

**任务1.1: MinerU适配层**
- 文件：`pdf2zh_next/mineru_adapter.py`
- 功能：封装MinerU调用接口

```python
class MinerUAdapter:
    """MinerU适配器 - 封装MinerU调用"""
    
    def __init__(self, model_path: str):
        """初始化MinerU
        
        Args:
            model_path: 模型路径，默认从环境变量或配置读取
        """
        self.model_path = model_path
        self.extractor = None
        
    def initialize(self):
        """初始化MinerU提取器"""
        from mineru_standalone.mineru_toolkit.extractor import MinerUTableExtractor
        
        self.extractor = MinerUTableExtractor(
            backend='transformers',
            model_name_or_path=self.model_path,
            device='cuda' if torch.cuda.is_available() else 'cpu'
        )
        
    def extract_from_pdf(self, pdf_path: str, dpi: int = 260):
        """从PDF提取结构化内容
        
        Returns:
            {
                'pages': [
                    {
                        'page_num': 1,
                        'blocks': [
                            {'type': 'text', 'content': '...', 'bbox': [...]},
                            {'type': 'formula', 'content': '...', 'latex': '...'},
                            {'type': 'table', 'html': '...', 'cells': [...]},
                            {'type': 'figure', 'image': ..., 'caption': '...'}
                        ]
                    }
                ]
            }
        """
        pass
```

**任务1.2: 本地存储管理器**
- 文件：`pdf2zh_next/storage_manager.py`

```python
class StorageManager:
    """本地存储管理器"""
    
    def __init__(self, storage_root: str = "storage"):
        self.storage_root = Path(storage_root)
        self.projects_dir = self.storage_root / "projects"
        self.index_file = self.storage_root / "index.json"
        
    def create_project(self, source_pdf: Path, metadata: dict) -> str:
        """创建新项目
        
        Returns:
            project_id: 项目唯一ID
        """
        project_id = self._generate_project_id()
        project_dir = self.projects_dir / project_id
        
        # 创建目录结构
        project_dir.mkdir(parents=True, exist_ok=True)
        (project_dir / "babeldoc").mkdir(exist_ok=True)
        (project_dir / "mineru").mkdir(exist_ok=True)
        
        # 复制源文件
        shutil.copy(source_pdf, project_dir / "source.pdf")
        
        # 保存元数据
        metadata.update({
            'project_id': project_id,
            'created_at': datetime.now().isoformat(),
            'source_file': source_pdf.name
        })
        (project_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding='utf-8'
        )
        
        # 更新索引
        self._update_index(project_id, metadata)
        
        return project_id
        
    def save_result(self, project_id: str, path_type: str, 
                   file_type: str, content: bytes | str):
        """保存翻译结果
        
        Args:
            project_id: 项目ID
            path_type: 'babeldoc' 或 'mineru'
            file_type: 'translated.pdf', 'dual.md', etc.
            content: 文件内容
        """
        pass
        
    def list_projects(self, filters: dict = None) -> list:
        """列出所有项目"""
        pass
        
    def get_project(self, project_id: str) -> dict:
        """获取项目详情"""
        pass
```

#### Track B: UI基础框架 (开发团队B)

**任务1.3: UI主题配置**
- 文件：`pdf2zh_next/gui_theme.py`

```python
import gradio as gr

def create_custom_theme():
    """创建自定义主题 - 参考reference-them"""
    
    return gr.themes.Soft(
        primary_hue=gr.themes.colors.orange,
        secondary_hue=gr.themes.colors.gray,
        neutral_hue=gr.themes.colors.gray,
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
        # 参考 reference-them 的配色
        body_background_fill="#F5F3F0",
        body_background_fill_dark="#2C2C2C",
        
        # 按钮样式
        button_primary_background_fill="#C17B5A",
        button_primary_background_fill_hover="#D4A574",
        button_primary_text_color="white",
        button_shadow="0 4px 6px rgba(0,0,0,0.1)",
        button_shadow_hover="0 6px 12px rgba(0,0,0,0.15)",
        
        # 卡片样式
        block_background_fill="white",
        block_border_width="1px",
        block_border_color="#E5E7EB",
        block_shadow="0 10px 30px rgba(0,0,0,0.05)",
        block_title_text_weight="600",
        
        # 输入框样式
        input_background_fill="white",
        input_border_color="#E5E7EB",
        input_border_width="1px",
        
        # 圆角
        radius_lg="12px",
        radius_md="8px",
        radius_sm="6px",
    )
```

**任务1.4: 自定义CSS**
- 文件：`pdf2zh_next/assets/custom.css`

```css
/* 完全参考 reference-them 的样式 */

:root {
    --primary-bg: #F5F3F0;
    --secondary-bg: #FFFFFF;
    --accent-bg: #E8E2DB;
    --text-primary: #2C2C2C;
    --text-secondary: #6B7280;
    --accent-color: #C17B5A;
    --accent-light: #D4A574;
    --border-color: #E5E7EB;
}

/* Hero Section */
.hero-section {
    background: linear-gradient(135deg, var(--primary-bg) 0%, var(--accent-bg) 100%);
    padding: 4rem 2rem;
    border-radius: 16px;
    margin-bottom: 2rem;
    position: relative;
    overflow: hidden;
}

.gradient-text {
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-light) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700;
}

/* Feature Cards */
.feature-card {
    background: var(--secondary-bg);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 2rem;
    transition: all 0.3s ease;
    height: 100%;
}

.feature-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 20px 40px rgba(0,0,0,0.1);
}

.feature-icon {
    width: 60px;
    height: 60px;
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-light) 100%);
    border-radius: 12px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: white;
    font-size: 1.5rem;
    margin-bottom: 1rem;
}

/* Progress Bar */
.progress-container {
    width: 100%;
    height: 4px;
    background: #E5E7EB;
    border-radius: 2px;
    overflow: hidden;
}

.progress-bar {
    height: 100%;
    background: linear-gradient(90deg, var(--accent-color) 0%, var(--accent-light) 100%);
    border-radius: 2px;
    transition: width 0.3s ease;
}

/* Status Indicators */
.status-indicator {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 8px;
}

.status-active { background-color: #10B981; }
.status-loading { background-color: #F59E0B; animation: pulse 1.5s infinite; }
.status-idle { background-color: #6B7280; }
.status-error { background-color: #EF4444; }

@keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.5; }
}

/* Buttons */
.custom-button-primary {
    background: linear-gradient(135deg, var(--accent-color) 0%, var(--accent-light) 100%);
    color: white;
    border: none;
    padding: 12px 24px;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
}

.custom-button-primary:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 12px rgba(193, 123, 90, 0.3);
}

/* File Browser */
.file-browser-item {
    background: white;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 1rem;
    margin: 0.5rem 0;
    cursor: pointer;
    transition: all 0.2s ease;
}

.file-browser-item:hover {
    background: var(--accent-bg);
    transform: translateX(4px);
}

/* Animations */
@keyframes fadeIn {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
}

.animate-fade-in {
    animation: fadeIn 0.6s ease-out;
}
```

**任务1.5: 背景特效**
- 文件：`pdf2zh_next/assets/hero_bg.js`

```javascript
// 简化版的背景动画效果 (不使用Vanta.js，使用纯CSS动画)
// 或者使用particles.js作为替代

function initHeroBackground() {
    // 创建动态背景粒子效果
    const canvas = document.createElement('canvas');
    canvas.id = 'hero-canvas';
    canvas.style.position = 'absolute';
    canvas.style.top = '0';
    canvas.style.left = '0';
    canvas.style.width = '100%';
    canvas.style.height = '100%';
    canvas.style.zIndex = '1';
    
    const heroSection = document.querySelector('.hero-section');
    if (heroSection) {
        heroSection.insertBefore(canvas, heroSection.firstChild);
        
        // 简单的粒子动画
        const ctx = canvas.getContext('2d');
        // ... 粒子动画代码
    }
}
```

---

### 第2周：核心功能实现

#### Track A: MinerU翻译流程

**任务2.1: MinerU翻译管道**
- 文件：`pdf2zh_next/mineru_pipeline.py`

```python
class MinerUTranslationPipeline:
    """MinerU翻译管道"""
    
    def __init__(self, settings, storage_manager):
        self.settings = settings
        self.storage = storage_manager
        self.adapter = MinerUAdapter(
            model_path=settings.mineru.model_path
        )
        self.translator = create_translator(settings)
        
    async def translate_pdf(self, pdf_path: Path, project_id: str):
        """翻译PDF文件
        
        流程:
        1. MinerU提取结构
        2. 翻译各个块
        3. 生成MD/HTML输出
        4. 保存到本地存储
        """
        
        # 1. 提取结构
        yield {"stage": "extract", "progress": 0.1, "message": "正在提取文档结构..."}
        structure = self.adapter.extract_from_pdf(pdf_path)
        
        # 2. 翻译
        yield {"stage": "translate", "progress": 0.3, "message": "正在翻译内容..."}
        translated_structure = await self._translate_structure(structure)
        
        # 3. 生成输出
        yield {"stage": "format", "progress": 0.7, "message": "正在生成输出文件..."}
        
        # 3.1 生成Markdown
        md_translated = self._to_markdown(translated_structure, mode='translated')
        md_dual = self._to_markdown(translated_structure, mode='dual')
        
        # 3.2 生成HTML
        html_translated = self._to_html(translated_structure, mode='translated')
        html_dual = self._to_html(translated_structure, mode='dual')
        
        # 4. 保存
        yield {"stage": "save", "progress": 0.9, "message": "正在保存文件..."}
        
        self.storage.save_result(project_id, 'mineru', 'translated.md', md_translated)
        self.storage.save_result(project_id, 'mineru', 'dual.md', md_dual)
        self.storage.save_result(project_id, 'mineru', 'translated.html', html_translated)
        self.storage.save_result(project_id, 'mineru', 'dual.html', html_dual)
        
        yield {"stage": "complete", "progress": 1.0, "message": "翻译完成！"}
        
    def _to_markdown(self, structure, mode='translated'):
        """转换为Markdown格式
        
        Args:
            mode: 'translated' 或 'dual'
        """
        md_lines = []
        
        for page in structure['pages']:
            md_lines.append(f"\n## 第 {page['page_num']} 页\n")
            
            for block in page['blocks']:
                if block['type'] == 'text':
                    if mode == 'dual':
                        md_lines.append(f"> {block['original']}\n")
                        md_lines.append(f"{block['translated']}\n")
                    else:
                        md_lines.append(f"{block['translated']}\n")
                        
                elif block['type'] == 'formula':
                    # LaTeX公式
                    if block.get('inline'):
                        md_lines.append(f"${block['latex']}$")
                    else:
                        md_lines.append(f"\n$$\n{block['latex']}\n$$\n")
                        
                elif block['type'] == 'table':
                    # 表格
                    md_lines.append(self._table_to_markdown(block))
                    
                elif block['type'] == 'figure':
                    # 图片
                    md_lines.append(f"\n![{block['caption_translated']}]({block['image_path']})\n")
                    if mode == 'dual':
                        md_lines.append(f"*原文: {block['caption_original']}*\n")
                    md_lines.append(f"*{block['caption_translated']}*\n")
        
        return '\n'.join(md_lines)
```

#### Track B: UI主界面实现

**任务2.2: 新UI主界面**
- 文件：`pdf2zh_next/gui_new.py`

核心结构见下一部分详细代码...

---

### 第3周：UI完善和文档浏览器

#### Track A: 文档浏览器

**任务3.1: 文档浏览器组件**
- 文件：`pdf2zh_next/document_viewer.py`

```python
class DocumentViewer:
    """文档浏览器 - 在Gradio中预览各种格式"""
    
    def __init__(self, storage_manager):
        self.storage = storage_manager
        
    def render_file(self, project_id: str, file_path: str):
        """渲染文件内容
        
        Returns:
            (content, file_type) - 用于Gradio显示
        """
        full_path = self.storage.get_file_path(project_id, file_path)
        
        if file_path.endswith('.pdf'):
            # PDF转图片预览
            return self._render_pdf(full_path), 'image'
            
        elif file_path.endswith('.md'):
            # Markdown渲染
            content = full_path.read_text(encoding='utf-8')
            html = markdown.markdown(content, extensions=['tables', 'fenced_code'])
            return html, 'html'
            
        elif file_path.endswith('.html'):
            # HTML直接显示
            content = full_path.read_text(encoding='utf-8')
            return content, 'html'
            
        elif file_path.endswith('.txt'):
            # 文本文件
            content = full_path.read_text(encoding='utf-8')
            return content, 'text'
```

#### Track B: UI完善

**任务3.2: 完整UI实现**

见下一个文件...

---

### 第4-5周：测试、优化和文档

- 单元测试
- 集成测试
- 性能优化
- 用户文档
- 部署准备

---

## 📝 下一步行动

1. **立即创建**: 基础文件结构
2. **测试MinerU**: 验证模型可用性
3. **UI原型**: 快速搭建UI框架
4. **并行开发**: 两个团队同时推进

准备好开始了吗？我将开始创建核心文件！

