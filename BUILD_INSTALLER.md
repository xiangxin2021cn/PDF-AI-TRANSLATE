# PDF文件翻译工具 Windows安装程序构建指南

本文档说明当前已验证的 Windows 桌面安装包构建方式。

当前推荐方案是 Electron + electron-builder + 随包 Python 运行时。这个路径会把当前已验证的 `.venv` 和 uv 的 CPython 基座组合成 `electron-app/python_portable`，再生成 NSIS 安装器和 portable 版本。它比旧 PyInstaller 单 exe 更适合本项目的 Gradio、BabelDOC、OCR、MinerU 等重依赖。

旧的 PyInstaller + Inno Setup 方案保留在本文后半部分作为历史备用方案，不再作为首选。

## 当前推荐：Electron + NSIS

### 前置要求

- Windows x64
- Node.js/npm 已安装
- 项目根目录 `.venv` 已同步并可运行
- `electron-app/package.json` 中已安装 Electron 和 electron-builder 依赖

### 一键构建

在项目根目录执行：

```powershell
cd electron-app
build_with_python.bat
```

该脚本会：

- 从项目 `.venv` 和 uv CPython 基座生成 `electron-app/python_portable`
- 将 `pdf2zh_next` 和 `mineru_standalone` 本地代码复制到随包运行时
- 通过 electron-builder 生成 NSIS 安装器和 portable 可执行文件

### 手动构建

```powershell
cd electron-app
..\.venv\Scripts\python.exe scripts\prepare_portable_runtime.py
npm install
$env:CSC_IDENTITY_AUTO_DISCOVERY="false"
npm run build-win
```

### 当前验证产物

构建成功后，`electron-app/dist/` 中应包含：

- `PDF文件翻译工具-2.5.0-win-x64.exe` - Windows NSIS 安装器
- `PDF文件翻译工具-2.5.0-Portable.exe` - 免安装 portable 版本
- `PDF文件翻译工具-2.5.0-win-x64.exe.blockmap` - 更新/校验辅助文件
- `win-unpacked/` - 解包版应用目录，可用于启动验证

### 启动验证

```powershell
cd ..
.\electron-app\dist\win-unpacked\PDF文件翻译工具.exe
```

验证重点：

- Electron 主进程能找到 `dist/win-unpacked/resources/python_portable/python.exe`
- 后端输出 `Running on local URL`
- 窗口能加载 `http://localhost:<port>`
- 输出目录为 `C:\Users\<用户名>\Documents\PDF文件翻译工具\output`

### 已知注意事项

- 首次启动随包 Python 运行时较慢，桌面壳等待时间已设置为 120 秒。
- 本地无代码签名证书时，构建日志会出现 `no signing info identified, signing is skipped`，不影响本地安装包生成。
- 如果 `dist/win-unpacked` 正在运行，Windows 会锁住 Python DLL，清理或重建前先关闭桌面程序及其随包 `python.exe` 子进程。

## 历史备用：PyInstaller + Inno Setup

以下内容是旧方案说明，仅在 Electron 方案不可用时作为参考。

本文档旧版说明如何使用 PyInstaller 和 Inno Setup Compiler 将 PDF文件翻译工具打包为 Windows 安装程序。

## 📋 前置要求

### 1. 安装Inno Setup Compiler
- 下载地址：https://jrsoftware.org/isdl.php
- 推荐版本：Inno Setup 6.x 或更高版本
- 安装到默认路径（通常是 `C:\Program Files (x86)\Inno Setup 6\`）

### 2. 确保项目环境完整
确保以下文件和目录存在：
- `pdf2zh_next/` - 主程序目录
- `.venv/` 或可用的 Python 虚拟环境
- `pyproject.toml` - 项目配置文件
- `README.md` - 项目说明文档
- `LICENSE` - 许可证文件
- `pdf2zh_desktop_app.py` - 桌面壳入口
- `pdf2zh_desktop.spec` - PyInstaller 配置
- `installer.iss` - Inno Setup 编译脚本

## 🚀 快速构建

### 方法一：PyInstaller + Inno Setup（推荐）

1. 打开命令提示符或PowerShell
2. 切换到项目根目录
3. 先构建桌面可执行文件：
```cmd
build_desktop.bat
```

4. 使用 Inno Setup 编译安装程序：
```cmd
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
```

脚本会自动：
- `build_desktop.bat` 会调用 PyInstaller 生成 `dist\PDF2ZH-Next-Desktop.exe`
- `installer.iss` 会把 `dist\PDF2ZH-Next-Desktop.exe` 打包为安装程序
- 安装程序输出到 `dist/` 目录

### 方法二：手动编译

1. 确保Inno Setup已正确安装
2. 双击 `installer.iss` 文件，或者：
3. 打开Inno Setup Compiler
4. 选择 "File" → "Open" → 选择 `installer.iss`
5. 点击 "Build" → "Compile" 或按 F9

## 📁 文件说明

### 核心文件

| 文件名 | 说明 |
|--------|------|
| `installer.iss` | Inno Setup编译脚本 |
| `start_gui.bat` | GUI启动脚本 |
| `build_desktop.bat` | PyInstaller 桌面程序构建脚本 |

### 生成的文件

构建成功后，会在 `dist/` 目录生成：
- `PDF文件翻译工具-Setup-v2.5.0.exe` - Windows安装程序

## ⚙️ 自定义配置

### 修改应用信息

编辑 `installer.iss` 文件顶部的定义：

```pascal
#define MyAppName "PDF文件翻译工具"
#define MyAppVersion "2.5.0"
#define MyAppPublisher "PDFMathTranslate Team"
#define MyAppURL "https://github.com/PDFMathTranslate/PDFMathTranslate-next"
```

### 添加应用图标

1. 准备一个 `.ico` 格式的图标文件
2. 将图标文件放置到 `pdf2zh_next/assets/app_icon.ico`
3. 取消注释 `installer.iss` 中的图标设置：
```pascal
SetupIconFile=pdf2zh_next\assets\app_icon.ico
```

### 修改安装选项

在 `installer.iss` 的 `[Setup]` 部分可以修改：
- `DefaultDirName` - 默认安装目录
- `PrivilegesRequired` - 所需权限级别
- `Compression` - 压缩算法
- `ArchitecturesAllowed` - 支持的架构

## 🔧 故障排除

### 常见问题

#### 1. 找不到Inno Setup编译器
**错误信息**：`未找到Inno Setup编译器`

**解决方案**：
- 确保已安装Inno Setup
- 检查安装路径是否为标准路径
- 将 `ISCC.exe` 添加到系统PATH环境变量

#### 2. 缺少必要文件
**错误信息**：`缺少必要文件: xxx`

**解决方案**：
- 确保在项目根目录运行构建脚本
- 检查虚拟环境是否完整：`pdf2zh-env/Scripts/python.exe`
- 确保所有源代码文件存在

#### 3. 编译失败
**错误信息**：`安装程序构建失败`

**解决方案**：
- 检查 `installer.iss` 文件语法
- 确保所有引用的文件路径正确
- 查看Inno Setup编译器的详细错误信息

### 调试技巧

1. **详细日志**：在Inno Setup编译器中启用详细输出
2. **分步测试**：先测试简单的配置，逐步添加复杂功能
3. **路径检查**：确保所有文件路径使用正确的分隔符

## 📦 分发安装程序

### 安装程序特性

生成的安装程序包含以下特性：
- **多语言支持**：中文简体和英文
- **用户友好**：现代化安装界面
- **灵活安装**：支持自定义安装路径
- **快捷方式**：自动创建开始菜单和桌面快捷方式
- **干净卸载**：完整的卸载功能

### 系统要求

- **操作系统**：Windows 7 SP1 或更高版本
- **架构**：x64 (64位)
- **Python**：建议安装Python 3.10-3.13（程序会检查）
- **磁盘空间**：约500MB可用空间

### 安装后使用

用户安装完成后可以通过以下方式启动程序：
1. 开始菜单 → PDF2ZH-Next
2. 桌面快捷方式（如果选择创建）
3. 直接运行安装目录下的 `start_gui.bat`

## 🔄 版本更新

更新版本时需要修改：
1. `pyproject.toml` 中的版本号
2. `installer.iss` 中的 `MyAppVersion`
3. `pdf2zh_next/main.py` 中的 `__version__`
4. 重新构建安装程序

## 📞 技术支持

如果在构建过程中遇到问题，请：
1. 查看本文档的故障排除部分
2. 检查Inno Setup官方文档
3. 在项目GitHub页面提交Issue

---

**注意**：本构建脚本假设您已经有一个完整的Python虚拟环境和所有必要的依赖项。如果需要从源码开始构建，请先按照项目README中的说明设置开发环境。
