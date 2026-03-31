# AgentTranslation — 多语种智能翻译Agent

拖拽上传文件，选择目标语言，一键翻译。支持术语管理、风格统一、自然度审校，翻译质量接近人工译员水平。

## 快速开始

**无需手动安装任何依赖**，启动脚本会自动处理一切。

| 系统 | 操作 |
|------|------|
| Mac | 终端运行 `bash start.sh`（首次），之后可直接 `./start.sh` |
| Windows | 双击 `start.bat` |

首次启动会自动安装 Python、Node.js 及所有依赖，大约需要 2-3 分钟。之后每次启动秒开。

启动成功后浏览器会自动打开 `http://localhost:8000`。

## 首次使用

### 1. 配置 API Key

翻译功能需要 LLM API 支持，首次使用前需要配置 API Key。两种方式任选其一：

**方式 A：通过界面配置（推荐）**

启动后点击右上角齿轮图标，在设置面板中填入 API Key 即可。

**方式 B：通过文件配置**

在项目根目录创建 `.env` 文件：
```
POE_API_KEY=你的API密钥
```
API Key 获取地址：https://poe.com/api/keys

### 2. 首次启动你会看到什么

```
============================================
  AgentTranslation - Starting...
============================================

[Setup] Creating Python virtual environment...     ← 首次会出现，约 1-2 分钟
[Setup] Installing Python dependencies...          ← 首次会出现
[Setup] Installing frontend dependencies...        ← 首次会出现
[Setup] Building frontend...                       ← 首次会出现

[OK] Python dependencies ready
[OK] Frontend ready

  Server starting at http://localhost:8000         ← 看到这行就说明启动成功了
```

第二次启动时这些 `[Setup]` 步骤会自动跳过。

### 3. 停止服务

在终端按 `Ctrl + C` 即可停止。

### 4. 常见问题

| 问题 | 解决方法 |
|------|----------|
| 端口 8000 被占用 | 关掉占用该端口的程序，或者停掉上一次没关干净的进程 |
| Windows 弹出防火墙提示 | 点击"允许访问"（仅本地通信，不联网） |
| Mac 提示"无法验证开发者" | 右键点击 `start.sh` → 打开 |
| 翻译报错 | 检查 API Key 是否配置正确（右上角齿轮 → 查看） |
| 首次启动特别慢 | 正常现象，在下载依赖包，请耐心等待 |

## 支持格式

| 类型 | 格式 |
|------|------|
| 演示文稿 | `.pptx` |
| 文档 | `.docx`、`.md`、`.html` |
| 字幕 | `.srt`、`.vtt`、`.ass` |
| 本地化 | `.json`、`.yaml`、`.po`、`.xliff`、`.xml` |

## 支持语言

中文（简/繁）、English、日本語、한국어、Français、Deutsch、Español、Português、Русский、Tiếng Việt、ไทย、Bahasa Indonesia、Монгол、Қазақ

## 翻译流程

```
上传文件 → 术语提取 → 人工审核术语表 → 翻译 → 自然度审校 → 下载译文
```

1. **术语提取** — AI 自动识别专业术语，匹配术语库已有条目
2. **术语审核** — 确认每个术语的翻译策略（严格翻译 / 保留原文 / 自由翻译）
3. **翻译** — 按语义分段并行翻译，术语约束贯穿全文
4. **自然度审校** — AI 二次润色，优化译文流畅度和表达习惯
5. **下载** — 保持原文件格式，支持同时下载翻译稿和审校稿

多语言翻译支持并行执行，多个目标语言同时翻译，无需排队等待。

## 配置

所有配置在 `config/settings.yaml`：

- **翻译模型** — 可切换不同 LLM（术语提取、翻译、审校各自独立配置）
- **并发数** — 调整同时翻译的段落数和语言数
- **翻译风格** — `config/styles/` 目录下可自定义风格模板
- **Prompt 模板** — `config/prompts/` 目录下可调整翻译和审校的 prompt

## 项目结构

```
├── start.sh / start.bat  — 一键启动
├── src/        — Python 后端（FastAPI、翻译引擎、格式解析、术语管理）
├── frontend/   — React + TypeScript 前端
├── config/     — 配置、prompt 模板、翻译风格
├── data/       — 运行时数据（数据库、缓存）
├── scripts/    — 开发脚本
└── tests/      — 测试
```
