# 多语种翻译 Agent 系统

基于多 Agent 协作的智能翻译系统，支持 PPT、Word、字幕等格式，术语提取、风格统一、质量审校。

## 快速开始

### 环境准备

```bash
pip install -r requirements.txt
export POE_API_KEY=your_poe_api_key
```

### CLI 翻译

```bash
# 单语言
python -m src.main translate presentation.pptx --target zh-CN

# 多语言（同时翻译成中文和越南语）
python -m src.main translate presentation.pptx -t zh-CN -t vi

# 指定风格
python -m src.main translate report.pptx --target ja --style technical
```

支持格式：`.pptx`、`.docx`、`.srt`、`.vtt`、`.ass`、`.md`、`.json`、`.yaml`、`.po`、`.xliff`、`.xml`、`.html`

### Web 界面

```bash
scripts/run_server.sh
```

浏览器打开 http://localhost:8000 ，拖拽上传文件、选择目标语言、点击翻译即可。
脚本会在首次运行时自动安装并构建 React 前端。

多语言翻译支持并行执行，默认并发数为 5，可通过 `config/settings.yaml` 里的 `translation.max_concurrent_languages_per_job` 调整。

### 桌面应用打包

```bash
# macOS
scripts/build_macos.sh

# Windows（需在 Windows 环境下执行）
scripts\build_windows.bat
```

## 目录结构

```
├── src/        — Python 后端（FastAPI 服务、翻译引擎、格式解析、术语管理）
├── frontend/   — React/TypeScript Web 前端
├── config/     — 配置文件、prompt 模板、翻译风格定义
├── data/       — 运行时数据（数据库、缓存、样本文件）
├── scripts/    — 构建脚本、打包配置、启动脚本
├── docs/       — 文档与原型
└── tests/      — 测试
```
