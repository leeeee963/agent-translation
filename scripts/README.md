# 构建与部署指南

## 日常开发

```bash
# 启动开发服务器（自动安装依赖、构建前端）
scripts/run_server.sh
```

浏览器打开 http://localhost:8000

---

## 打包 macOS 桌面应用

打包后的应用是**完全独立的**，用户不需要安装 Python、Node.js 或任何依赖。

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

---

## 功能更新后重新打包

改完代码后，重新运行构建脚本即可，脚本会自动：

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
