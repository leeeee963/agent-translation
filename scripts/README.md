# 构建与部署指南

## 日常开发

```bash
# 启动开发服务器（自动安装依赖、构建前端）
scripts/run_server.sh
```

浏览器打开 http://localhost:8000

---

## 打包桌面应用

打包后的应用是**完全独立的**，用户不需要安装 Python、Node.js 或任何依赖。

### macOS（在 Mac 上执行，同时支持 Intel + Apple Silicon）

**前提：** 需要安装 [python.org 官方 universal2 安装包](https://www.python.org/downloads/macos/)（不是 Homebrew 的）。
下载页面选 **"macOS 64-bit universal2 installer"**，安装后会出现在 `/usr/local/bin/python3.12`。

```bash
scripts/build_macos.sh
```

脚本会自动创建 universal2 venv、安装依赖、构建前端、打包 app。
产出的 `dist/AgentTranslation.app` 同时支持 Intel 和 Apple Silicon Mac。

分发给用户：
```bash
zip -r AgentTranslation-Mac.zip dist/AgentTranslation.app
```

### Windows（必须在 Windows 上执行）

```bat
scripts\build_windows.bat
```

产出：`dist\AgentTranslation\AgentTranslation.exe`

分发给用户：把整个 `dist\AgentTranslation\` 文件夹打成 zip。

> PyInstaller 不支持跨平台编译，macOS 上无法生成 Windows exe，反之亦然。
> 如果没有 Windows 电脑，可以用 GitHub Actions 自动构建（见下方）。

### Windows 构建环境要求

在 Windows 机器上需要预先安装：
1. **Python 3.11+** — https://python.org
2. **Node.js 18+** — https://nodejs.org
3. 安装 Python 依赖：`pip install -r requirements.txt`

之后运行 `scripts\build_windows.bat` 即可。

---

## 功能更新后重新打包

改完代码后，重新运行对应平台的构建脚本即可，脚本会自动：

1. 重新构建前端（`npm run build`）
2. 安装打包工具（`pyinstaller`、`pywebview`）
3. 重新打包整个应用

**不需要手动做任何额外步骤。**

---

## 文件说明

| 文件 | 用途 |
|------|------|
| `run_server.sh` | 开发服务器启动脚本 |
| `build_macos.sh` | macOS .app 打包脚本 |
| `build_macos.spec` | macOS PyInstaller 配置 |
| `build_windows.bat` | Windows exe 打包脚本 |
| `build_windows.spec` | Windows PyInstaller 配置 |
