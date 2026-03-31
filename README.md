# 多语种翻译 Agent 系统

基于多 Agent 协作的智能翻译系统，支持 PPT、Word、字幕等格式，术语提取、风格统一、质量审校。

## 快速开始

**Mac 用户：** 双击 `start.sh`（或终端运行 `./start.sh`）
**Windows 用户：** 双击 `start.bat`

脚本会自动检查并安装所有依赖（Python、Node.js），首次启动需要几分钟，之后秒开。
启动后浏览器会自动打开 http://localhost:8000

## 使用

拖拽上传文件、选择目标语言、点击翻译即可。

支持格式：`.pptx`、`.docx`、`.srt`、`.vtt`、`.ass`、`.md`、`.json`、`.yaml`、`.po`、`.xliff`、`.xml`、`.html`

多语言翻译支持并行执行，默认并发数为 5，可通过 `config/settings.yaml` 调整。

## 目录结构

```
├── start.sh / start.bat  — 一键启动（用户用这个）
├── src/        — Python 后端（FastAPI 服务、翻译引擎、格式解析、术语管理）
├── frontend/   — React/TypeScript Web 前端
├── config/     — 配置文件、prompt 模板、翻译风格定义
├── data/       — 运行时数据（数据库、缓存、样本文件）
├── scripts/    — 开发脚本
├── docs/       — 文档与原型
└── tests/      — 测试
```
