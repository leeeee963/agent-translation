# 多语种翻译 Agent 系统

基于多 Agent 协作的智能翻译系统，支持 PPT、字幕等格式，术语提取、风格统一、质量审校。

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

支持格式：`.pptx`、`.srt`、`.vtt`、`.ass`

### Web 界面

```bash
python -m uvicorn src.server:app --reload --port 8000
```

浏览器打开 http://localhost:8000 ，拖拽上传文件、选择目标语言、点击翻译即可。

如果使用 `./run_server.sh` 启动，脚本会在首次运行时自动安装并构建新的 React 前端。
同一文件下的多语言翻译现在支持并行执行，默认并发数为 5，可通过 `config/settings.yaml` 里的 `translation.max_concurrent_languages_per_job` 调整。

## 目录结构

- `src/` — 核心代码（orchestrator、parser、translator、reviewer 等）
- `frontend/` — 新的 React Web 前端源码
- `web/` — 旧静态前端（仅兜底保留）
- `config/` — 配置与 prompt 模板

## 文档

- [需求设计文档](./需求设计文档.md)
- [开发计划](./开发计划.md)
