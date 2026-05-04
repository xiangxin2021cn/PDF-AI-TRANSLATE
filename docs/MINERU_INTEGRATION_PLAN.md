# MinerU集成实施计划 - 方案A

## 📋 总体策略

在原GUI（`pdf2zh_next/gui.py`）中添加MinerU Tab，保留所有现有功能和设置。

## 🎯 核心原则

1. **不破坏现有功能** - 所有BabelDOC翻译功能保持不变
2. **最大化代码复用** - 复用现有的翻译引擎设置、速率限制等
3. **统一用户体验** - 在同一界面中提供两种翻译路径
4. **清晰的功能分离** - BabelDOC和MinerU各自的特定选项分开显示

## 📊 配置共用分析

### ✅ 可以共用的配置（必须复用）

#### 1. 翻译引擎设置
- 所有20+翻译服务（OpenAI, Azure, DeepL, Google等）
- API密钥、端点、模型等详细配置
- 敏感字段处理

#### 2. 通用翻译选项
- `lang_in`, `lang_out` - 源语言和目标语言
- `custom_system_prompt` - 自定义系统提示
- `glossaries` - 术语表
- `ignore_cache` - 缓存控制
- `min_text_length` - 最小翻译文本长度

#### 3. 速率限制设置
- `qps` - 每秒查询数
- `pool_max_workers` - 线程池最大工作线程数
- Rate limit mode (RPM/Concurrent/Custom)

### ❌ 不适用于MinerU的配置

#### BabelDOC特定的PDF处理选项
- `skip_clean`, `disable_rich_text_translate`, `enhance_compatibility`
- `split_short_lines`, `short_line_split_factor`
- `translate_table_text`
- `formular_font_pattern`, `formular_char_pattern`
- BabelDOC高级选项（`merge_alternating_line_numbers`等）

#### PDF输出格式选项
- `no_mono`, `no_dual` - MinerU输出Markdown/HTML，不是PDF
- `dual_translate_first`, `use_alternating_pages_dual`
- `watermark_output_mode`

### ⚠️ OCR相关配置

**重要发现**:
- MinerU本身就是强大的OCR工具（使用Qwen2VL视觉语言模型）
- **不需要**BabelDOC的`ocr_workaround`和`auto_enable_ocr_workaround`
- MinerU有自己的配置：
  - `model_path` - 模型路径
  - `backend` - transformers或http-client
  - `dpi` - 图像DPI

## 🏗️ UI结构设计

```
原GUI (gui.py)
├─ Tab 1: "PDF Translation" (现有，保持不变)
│   ├─ 文件上传
│   ├─ 翻译引擎选择
│   ├─ 语言设置
│   ├─ PDF输出选项
│   ├─ BabelDOC高级选项
│   └─ 翻译按钮
│
├─ Tab 2: "MinerU Translation" (新增)
│   ├─ 文件上传
│   ├─ 输出格式选择
│   │   ├─ Markdown
│   │   ├─ HTML
│   │   └─ Both
│   ├─ MinerU特定选项
│   │   ├─ Model Path (默认: opendatalab/MinerU2.5-2509-1.2B)
│   │   ├─ Backend (transformers/http-client)
│   │   └─ DPI (默认: 260)
│   ├─ 复用翻译引擎设置（从Tab 1获取）
│   ├─ 复用通用翻译选项（从Tab 1获取）
│   ├─ 项目管理
│   │   ├─ 历史项目列表
│   │   ├─ 项目搜索/过滤
│   │   └─ 项目删除
│   ├─ 文档浏览器
│   │   ├─ 源文件预览
│   │   ├─ 翻译结果预览
│   │   └─ 格式切换（Markdown/HTML）
│   └─ 翻译按钮
│
└─ Tab 3: "Settings" (现有，保持不变)
    └─ 所有配置选项
```

## 🔧 实施步骤

### 步骤1: 准备工作
- [x] 创建MinerU适配器 (`mineru_adapter.py`)
- [x] 创建存储管理器 (`storage_manager.py`)
- [x] 创建MinerU翻译管道 (`mineru_pipeline.py`)
- [x] 创建文档浏览器 (`document_viewer.py`)
- [x] 优化主题配置 (`gui_theme.py`)

### 步骤2: 在gui.py中添加MinerU Tab

#### 2.1 导入必要的模块
```python
from pdf2zh_next.mineru_pipeline import MinerUTranslationPipeline
from pdf2zh_next.storage_manager import StorageManager
from pdf2zh_next.document_viewer import DocumentViewer
from pdf2zh_next.gui_theme import get_vanta_js, get_custom_css
```

#### 2.2 初始化组件
```python
# 在全局初始化部分
storage_manager = StorageManager("storage")
document_viewer = DocumentViewer(max_pdf_pages=10)
```

#### 2.3 创建MinerU Tab
在现有的Tabs中添加新Tab：
```python
with gr.Tabs() as tabs:
    # 现有的PDF Translation Tab
    with gr.Tab("PDF Translation"):
        # ... 现有代码 ...
    
    # 新增的MinerU Translation Tab
    with gr.Tab("MinerU Translation"):
        gr.Markdown("# 🦅 MinerU智能翻译")
        gr.Markdown("使用MinerU视觉语言模型进行文档识别和翻译，输出Markdown/HTML格式")
        
        with gr.Row():
            with gr.Column(scale=1):
                # 文件上传
                mineru_file = gr.File(
                    label="上传PDF文件",
                    file_types=[".pdf"],
                    type="filepath"
                )
                
                # 输出格式选择
                output_format = gr.Radio(
                    choices=["Markdown", "HTML", "Both"],
                    label="输出格式",
                    value="Markdown"
                )
                
                # MinerU特定选项
                with gr.Accordion("MinerU设置", open=False):
                    mineru_model_path = gr.Textbox(
                        label="模型路径",
                        value="opendatalab/MinerU2.5-2509-1.2B",
                        info="HuggingFace模型ID或本地路径"
                    )
                    mineru_backend = gr.Radio(
                        choices=["transformers", "http-client"],
                        label="后端",
                        value="transformers"
                    )
                    mineru_dpi = gr.Number(
                        label="DPI",
                        value=260,
                        precision=0
                    )
                
                # 翻译按钮
                mineru_translate_btn = gr.Button(
                    "开始翻译",
                    variant="primary"
                )
                
                # 进度显示
                mineru_progress = gr.Textbox(
                    label="翻译进度",
                    interactive=False
                )
            
            with gr.Column(scale=1):
                # 项目管理
                gr.Markdown("## 📁 项目管理")
                project_list = gr.Dataframe(
                    headers=["项目ID", "文件名", "格式", "创建时间"],
                    label="历史项目"
                )
                refresh_projects_btn = gr.Button("刷新列表")
                
                # 文档浏览器
                gr.Markdown("## 👁️ 文档预览")
                doc_viewer_output = gr.HTML(label="预览")
```

#### 2.4 实现翻译逻辑
```python
async def mineru_translate_handler(
    file_path,
    output_format,
    model_path,
    backend,
    dpi,
    progress=gr.Progress()
):
    """MinerU翻译处理函数"""
    # 1. 获取当前的翻译引擎设置（从Tab 1复用）
    translate_settings = settings.clone()
    
    # 2. 更新MinerU特定设置
    translate_settings.mineru.model_path = model_path
    translate_settings.mineru.backend = backend
    translate_settings.mineru.dpi = dpi
    translate_settings.pdf.output_format = output_format.lower()
    
    # 3. 创建翻译管道
    pipeline = MinerUTranslationPipeline(
        translate_settings.to_settings_model(),
        storage_manager
    )
    
    # 4. 执行翻译
    project_id = None
    async for event in pipeline.translate_pdf(file_path):
        if event['type'] == 'progress':
            progress(event['progress'] / 100, desc=event['message'])
        elif event['type'] == 'complete':
            project_id = event['project_id']
    
    # 5. 返回结果
    return f"翻译完成！项目ID: {project_id}"

# 绑定事件
mineru_translate_btn.click(
    fn=mineru_translate_handler,
    inputs=[
        mineru_file,
        output_format,
        mineru_model_path,
        mineru_backend,
        mineru_dpi
    ],
    outputs=[mineru_progress]
)
```

### 步骤3: 集成Vanta.js飞鸟特效

在创建Gradio Blocks时添加：
```python
with gr.Blocks(
    theme=create_custom_theme(),
    css=get_custom_css(),
    head=get_vanta_js()  # 添加Vanta.js
) as demo:
    # ... UI代码 ...
```

### 步骤4: 测试和验证

#### 测试清单
- [ ] BabelDOC翻译功能正常
- [ ] MinerU翻译功能正常
- [ ] 翻译引擎设置共用正常
- [ ] 项目管理功能正常
- [ ] 文档浏览器功能正常
- [ ] Vanta.js特效显示正常
- [ ] 深色模式文字可见
- [ ] 标题样式正确（橘色、居中、大字）

## 📝 注意事项

1. **设置共用机制**:
   - 使用全局的`settings`对象
   - MinerU Tab从`settings`获取翻译引擎配置
   - 用户在任一Tab修改设置，两个Tab都生效

2. **错误处理**:
   - MinerU模型加载失败时的友好提示
   - 翻译失败时的错误信息显示
   - 文件格式验证

3. **性能优化**:
   - 大文件处理的进度显示
   - 异步翻译避免UI阻塞
   - 文档预览的分页加载

4. **用户体验**:
   - 清晰的功能说明
   - 合理的默认值
   - 友好的错误提示

## 🎨 主题优化

### 已完成
- [x] 添加Vanta.js飞鸟背景特效
- [x] 修复深色模式文字颜色问题
- [x] 优化标题样式（橘色渐变、居中、更大字号）
- [x] 添加渐变效果和动画

### 特效配置
- 背景颜色: #F5F3F0
- 鸟的颜色1: #C17B5A
- 鸟的颜色2: #D4A574
- 鸟的数量: 3只
- 飞行速度: 适中

## 🚀 下一步

1. 在`gui.py`中实施上述修改
2. 测试所有功能
3. 优化用户体验
4. 编写用户文档

