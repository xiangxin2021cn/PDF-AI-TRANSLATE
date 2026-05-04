# 新功能使用指南

## 🎉 新增功能

### 1. MinerU翻译路径

除了原有的PDF格式翻译（BabelDOC），现在支持结构化输出（MinerU）：

- ✅ **Markdown格式** - 便于编辑和版本控制
- ✅ **HTML格式** - 美观的网页展示
- ✅ **双语对照** - 原文和译文并排显示
- ✅ **大模型友好** - 结构化格式便于AI分析

### 2. 本地存储管理

所有翻译结果统一存储到本地，方便管理：

- ✅ **项目管理** - 查看所有翻译项目
- ✅ **文件浏览** - 预览翻译结果
- ✅ **历史记录** - 保留所有翻译历史
- ✅ **一键删除** - 清理不需要的项目

### 3. 现代化UI

全新的用户界面，参考reference-them设计：

- ✅ **美观设计** - 温暖橙色系配色
- ✅ **响应式布局** - 适配不同屏幕
- ✅ **实时预览** - 在线查看翻译结果
- ✅ **进度显示** - 实时翻译进度

---

## 🚀 快速开始

### 启动新UI

```bash
# 使用启动脚本
py launch_new_ui.py
```

浏览器会自动打开 `http://127.0.0.1:7860`

### 使用步骤

1. **上传PDF文件**
   - 点击"选择PDF文件"
   - 选择要翻译的PDF

2. **选择翻译路径**
   - **PDF格式** - 保持原PDF格式（BabelDOC）
   - **Markdown/HTML** - 结构化输出（MinerU）

3. **配置翻译选项**
   - 源语言：en, zh, ja, ko, fr, de, es, ru
   - 目标语言：zh, en, ja, ko, fr, de, es, ru
   - 输出格式（MinerU）：Markdown, HTML

4. **开始翻译**
   - 点击"🚀 开始翻译"
   - 等待翻译完成
   - 下载结果文件

5. **查看结果**
   - 切换到"📁 项目管理"标签
   - 查看所有翻译项目
   - 切换到"👁️ 文档浏览"标签
   - 在线预览翻译结果

---

## 📖 详细功能说明

### 翻译界面

**上传文档**:
- 支持PDF格式
- 自动提取文档标题
- 可手动修改标题

**翻译选项**:
- **翻译路径**:
  - `PDF格式` - 使用BabelDOC，保持原PDF格式和布局
  - `Markdown/HTML` - 使用MinerU，输出结构化文档
  
- **输出格式**（仅MinerU）:
  - `Markdown` - 适合编辑和版本控制
  - `HTML` - 美观的网页展示
  
- **语言选择**:
  - 源语言：文档原始语言
  - 目标语言：翻译目标语言

**翻译进度**:
- 实时显示翻译状态
- 进度条显示完成百分比
- 详细信息显示当前阶段

**翻译结果**:
- 自动保存到本地存储
- 提供下载链接
- 记录项目ID

### 项目管理

**项目列表**:
- 显示所有翻译项目
- 包含项目ID、标题、状态、创建时间、翻译路径
- 支持刷新

**项目详情**:
- 输入项目ID查看详情
- 显示完整的项目信息
- 包含所有结果文件列表

**项目操作**:
- 查看文件 - 跳转到文档浏览
- 删除项目 - 删除项目及所有文件

### 文档浏览

**文件选择**:
- 输入项目ID
- 自动加载文件列表
- 包含源文件和所有结果文件

**文件预览**:
- **PDF** - 转换为图片显示
- **Markdown** - 渲染为HTML显示
- **HTML** - 直接显示
- **文本** - 格式化显示

**预览特性**:
- 支持LaTeX公式（MathJax）
- 支持表格
- 支持图片
- 响应式布局

### 设置页面

**翻译引擎**:
- 显示当前配置
- 支持20+翻译服务
- 需要通过配置文件修改

**MinerU配置**:
- 显示当前MinerU配置
- 后端类型
- 模型路径
- DPI设置

---

## 🔧 高级用法

### 编程接口

#### 使用MinerU翻译

```python
from pdf2zh_next.config.model import SettingsModel
from pdf2zh_next.storage_manager import StorageManager
from pdf2zh_next.mineru_pipeline import MinerUTranslationPipeline
import asyncio

# 1. 加载配置
settings = SettingsModel()

# 2. 创建存储管理器
storage = StorageManager("storage")

# 3. 创建翻译管道
pipeline = MinerUTranslationPipeline(settings, storage)

# 4. 创建项目
project_id = storage.create_project(
    source_pdf="paper.pdf",
    metadata={
        'title': 'My Paper',
        'lang_in': 'en',
        'lang_out': 'zh',
        'translation_path': 'mineru',
        'output_formats': ['markdown', 'html']
    }
)

# 5. 执行翻译
async def translate():
    async for event in pipeline.translate_pdf("paper.pdf", project_id):
        print(f"[{event['stage']}] {event['progress']:.0%} - {event['message']}")

asyncio.run(translate())

# 6. 获取结果
project = storage.get_project(project_id)
print(f"结果文件: {project['results']}")
```

#### 使用文档浏览器

```python
from pdf2zh_next.document_viewer import DocumentViewer

viewer = DocumentViewer()

# 预览PDF（转图片）
images = viewer.render_pdf("document.pdf", pages=[1, 2, 3], dpi=150)

# 预览Markdown（渲染为HTML）
html = viewer.render_markdown("document.md", include_mathjax=True)

# 预览HTML
html = viewer.render_html("document.html")

# 自动识别文件类型
html, images = viewer.render_file("document.pdf")
```

#### 使用存储管理器

```python
from pdf2zh_next.storage_manager import StorageManager

storage = StorageManager("storage")

# 创建项目
project_id = storage.create_project(
    source_pdf="paper.pdf",
    metadata={'title': 'My Paper'}
)

# 保存结果
storage.save_result(
    project_id=project_id,
    path_type='mineru',
    file_name='translated.md',
    content='# Translated Content'
)

# 列出所有项目
projects = storage.list_projects(sort_by='created_at')

# 获取项目详情
project = storage.get_project(project_id)

# 获取文件路径
file_path = storage.get_file_path(project_id, 'mineru/translated.md')

# 删除项目
storage.delete_project(project_id)
```

---

## 📁 文件结构

### 存储目录

```
storage/
├── projects/
│   ├── 20250104_143022_a1b2c3d4/
│   │   ├── source.pdf              # 源文件
│   │   ├── metadata.json           # 项目元数据
│   │   ├── babeldoc/               # BabelDOC输出
│   │   │   ├── translated.pdf      # 译文PDF
│   │   │   ├── dual.pdf            # 双语对照PDF
│   │   │   └── vocabulary.txt      # 专业词汇
│   │   └── mineru/                 # MinerU输出
│   │       ├── translated.md       # 译文Markdown
│   │       ├── dual.md             # 双语对照Markdown
│   │       ├── translated.html     # 译文HTML
│   │       ├── dual.html           # 双语对照HTML
│   │       └── images/             # 图片文件夹
│   └── ...
└── index.json                      # 项目索引
```

### 项目元数据

```json
{
    "project_id": "20250104_143022_a1b2c3d4",
    "title": "Scientific Paper",
    "status": "completed",
    "created_at": "2025-01-04T14:30:22",
    "updated_at": "2025-01-04T14:35:10",
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

---

## ❓ 常见问题

### Q: 如何选择翻译路径？

**A**: 根据您的需求选择：

- **PDF格式（BabelDOC）**:
  - ✅ 需要保持原PDF格式和布局
  - ✅ 需要打印或分享PDF
  - ✅ 需要专业词汇表
  
- **Markdown/HTML（MinerU）**:
  - ✅ 需要编辑翻译结果
  - ✅ 需要版本控制
  - ✅ 需要在网页上展示
  - ✅ 需要给大模型分析

### Q: 两种路径的翻译质量一样吗？

**A**: 是的！两种路径使用**同一个翻译引擎**，翻译质量完全一致。区别只在于输出格式。

### Q: 如何配置翻译引擎？

**A**: 通过配置文件或命令行参数配置。支持的翻译引擎包括：
- OpenAI
- Azure OpenAI
- Google Translate
- DeepL
- SiliconFlow
- Ollama
- 等20+种服务

### Q: MinerU需要GPU吗？

**A**: 
- **本地模式（transformers）**: 建议使用GPU，但CPU也可以运行（较慢）
- **HTTP模式（http-client）**: 不需要GPU，连接远程服务器

### Q: 如何查看历史翻译？

**A**: 
1. 切换到"📁 项目管理"标签
2. 查看项目列表
3. 输入项目ID查看详情
4. 切换到"👁️ 文档浏览"标签预览文件

### Q: 如何删除不需要的项目？

**A**:
1. 切换到"📁 项目管理"标签
2. 输入要删除的项目ID
3. 点击"🗑️ 删除项目"按钮

---

## 🎓 技术细节

### 翻译流程（MinerU路径）

```
1. MinerU识别 (30%)
   - 使用Qwen2VL模型识别文档结构
   - 提取文本、公式、表格、图片
   ↓
2. 提取文本块 (10%)
   - 识别需要翻译的文本
   - 过滤公式和特殊内容
   ↓
3. 批量翻译 (50%)
   - 使用原应用翻译引擎
   - 充分利用缓存
   - 速率限制控制
   ↓
4. 生成输出 (10%)
   - 生成Markdown格式
   - 生成HTML格式
   - 生成双语对照版本
```

### 文档结构格式

```python
{
    'source': 'path/to/file.pdf',
    'total_pages': 10,
    'pages': [
        {
            'page_num': 1,
            'blocks': [
                {
                    'type': 'text',
                    'content': '文本内容'
                },
                {
                    'type': 'formula',
                    'latex': '$$E=mc^2$$',
                    'inline': False
                },
                {
                    'type': 'table',
                    'html': '<table>...</table>',
                    'markdown': '| A | B |'
                },
                {
                    'type': 'figure',
                    'image': PIL.Image,
                    'caption': '图片说明'
                }
            ]
        }
    ]
}
```

---

## 📞 获取帮助

如果遇到问题：

1. 查看日志输出
2. 检查配置文件
3. 查看文档
4. 提交Issue

---

## 🎉 开始使用

```bash
# 启动新UI
py launch_new_ui.py

# 访问
http://127.0.0.1:7860
```

享受全新的翻译体验！🚀

