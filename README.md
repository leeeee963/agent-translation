# AgentTranslation — 多语种智能翻译Agent

拖拽上传文件，选择目标语言，一键翻译。支持术语管理、风格统一、自然度审校，翻译质量接近人工译员水平。

## 技术栈

- **后端**：Python 3.11+ / FastAPI / httpx（调用 SudoCode OpenAI 兼容接口）
- **前端**：React 18 + TypeScript / Vite / Tailwind CSS 4 / Radix UI
- 前端构建产物 `frontend/dist/` 由 FastAPI 作为静态资源直接托管

## 本地开发

```bash
# 1. 后端依赖
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. 前端依赖 + 构建
cd frontend
npm install
npm run build
cd ..

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，至少填入：
#   SUDO_API_KEY=你的 LLM 密钥
#   ACCESS_PASSWORD=你给前端登录页设置的密码（本地也要设，否则无法登录）

# 4. 启动
python -m uvicorn src.server:app --reload --port 8000
```

打开 `http://localhost:8000` 即可。

前端热更新模式（API 自动代理到 8000）：

```bash
cd frontend && npm run dev
```

API Key 获取地址：https://sudocode.us/

## 访问鉴权

项目自带一个**共享密码门禁**：所有 `/api/*` 请求都要登录，前端启动时会显示登录页。

- 在 `.env` 中设置 `ACCESS_PASSWORD=你的密码`，重启即可生效
- `SESSION_SECRET` 用于签名 cookie；不设的话每次重启都会随机生成（导致已登录用户掉线）。**部署到公网时必须设置一个固定值**
- 没有「注册」概念，所有人共用同一个密码、同一个术语库；后续做用户系统时再升级
- 登录后只能查看 LLM 配置和 Prompt（只读），不能在线修改——这些只能改代码 / `.env` 后重新部署

## 部署

项目自带一个 `Dockerfile`，专门给生产部署（Zeabur / Vercel / Railway / 自托管 Docker host 等）用。**本地开发不需要 Docker**，按上面「本地开发」走即可。

### 部署到 Zeabur

1. 把项目 push 到 GitHub
2. 在 Zeabur Dashboard 新建 Project → Add Service → Deploy from GitHub，选这个仓库
3. 配置环境变量（必填）：
   - `SUDO_API_KEY` — LLM 密钥
   - `ACCESS_PASSWORD` — 前端登录页的密码
   - `SESSION_SECRET` — 用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成一个固定值
4. Zeabur 自动检测 `Dockerfile` 并构建部署，注入 `$PORT`
5. 部署完成后绑定域名，访问域名 → 登录页 → 输密码 → 开始用

### ⚠️ 当前限制（首次上线版）

- **数据每次重启清零**：历史任务和术语库都存在容器内的 SQLite，Zeabur 容器无状态，重新部署或重启后清空。后续会迁到 Postgres 解决。
- **上传 / 下载文件**：源文件和翻译结果存在容器临时目录，重启后下载链接失效。建议翻译完即下载。

## 支持格式

| 类型 | 格式 |
|------|------|
| 演示文稿 | `.pptx` |
| 文档 | `.docx`、`.md`、`.html`、`.txt` |
| 字幕 | `.srt`、`.vtt`、`.ass` |
| 本地化 | `.json`、`.yaml`、`.po`、`.xliff`、`.xml` |

## 支持语言

中文（简/繁）、English、日本語、한국어、Français、Deutsch、Español、Português、Русский、Tiếng Việt、ไทย、Bahasa Indonesia、Монгол、Қазақ

## 翻译流程

```
上传文件 → 术语提取 → 人工审核术语表 → 翻译 → 自然度审校 → 下载译文
```

1. **术语提取** — AI 自动识别专业术语，匹配术语库已有条目
2. **术语审核** — 确认每个术语的翻译策略（约束 / 保留 / 自由）
3. **翻译** — 按语义分段并行翻译，术语约束贯穿全文
4. **自然度审校** — AI 二次润色，优化译文流畅度和表达习惯
5. **下载** — 保持原文件格式，支持同时下载翻译稿和审校稿

多语言翻译支持并行执行，多个目标语言同时翻译，无需排队等待。

## 术语库

支持术语库的导入导出和持久化管理，翻译时自动匹配已有术语。

### 导入术语

在术语库页面选择域后，点击「导入」上传 CSV/TSV 文件。文件格式：

- **列名为语言代码**（如 `en`, `zh-CN`, `ja`），无需特殊的 `source` 列
- **可选列**：`strategy`（约束/保留/自由，默认约束）、`context`（领域含义）
- 可点击弹窗内「下载 CSV 模板」获取包含所有支持语言的示例文件

### 导出术语

在术语库页面直接点击 CSV / TSV / JSON 按钮下载当前域的术语数据。

### 翻译策略

| 策略值 | 含义 | 说明 |
|--------|------|------|
| `hard` | 约束 | 锁定译文，严格遵守 |
| `keep_original` | 保留 | 保持原文，跳过翻译 |
| `skip` | 自由 | 放开限制，自行翻译 |

## 配置

所有配置在 `config/settings.yaml`：

- **翻译模型** — 可切换不同 LLM（术语提取、翻译、审校各自独立配置）
- **并发数** — 调整同时翻译的段落数和语言数
- **翻译风格** — `config/styles/` 目录下可自定义风格模板
- **Prompt 模板** — `config/prompts/` 目录下可调整翻译和审校的 prompt

## 项目结构

```
├── src/        — Python 后端（FastAPI、翻译引擎、格式解析、术语管理）
├── frontend/   — React + TypeScript 前端
├── config/     — 配置、prompt 模板、翻译风格
├── data/       — 运行时数据（数据库、缓存，gitignore）
├── docs/       — 文档
└── tests/      — 测试
```
