# 保单簿 PolicyBook 开发指导手册

| 项 | 内容 |
|---|---|
| 版本 | v1.0 |
| 日期 | 2026-09-15 |
| 适用对象 | 开发者本人，以及 Claude Code / Antigravity / grok build 等编码 Agent |
| 上游文档 | docs/PRD.md（功能范围以 PRD 为准，本手册只规定怎么做） |

---

## 目录

1. 使用方式与编码 Agent 协作规则
2. 技术栈
3. Windows 11 开发环境
4. 仓库结构
5. 后端设计
6. 模型接入层与提示词
7. 前端设计系统
8. 核心算法
9. 测评模式
10. 里程碑与分阶段提示词
11. 测试策略
12. Docker 与 NAS 部署
13. 开发红线清单

---

## 1. 使用方式与编码 Agent 协作规则

### 1.1 文档的权威顺序

`docs/PRD.md` 决定做什么；本手册决定怎么做；仓库根目录的 `AGENTS.md` 是给编码 Agent 的精简规则，内容与本手册第 13 章一致。三者冲突时以 PRD 为准，并由人工修订文档后再继续开发。

### 1.2 三种编码工具的接入方式

| 工具 | 规则文件 | 做法 |
|---|---|---|
| Claude Code | `CLAUDE.md` | 在 `CLAUDE.md` 中只写一行：开始任何工作前先完整阅读 `AGENTS.md`、`docs/PRD.md` 与 `docs/DEV-GUIDE.md` 中与当前阶段相关的章节 |
| Antigravity | 以工具当前版本支持的规则机制为准 | 若不会自动读取 `AGENTS.md`，在每个阶段提示词开头显式要求先读取 |
| grok build | 同上 | 同上 |

建议同一阶段只用一个工具完成，阶段结束后提交并打 tag，再换工具进入下一阶段，避免多个 Agent 交叉修改同一文件。

### 1.3 报告纪律

编码 Agent 汇报进度时必须遵守以下规则，未满足视为该项未完成：

1. 声称「测试通过」时，附上测试命令及其原始输出的末尾部分。
2. 声称「接口可用」时，附上实际请求命令与响应体。
3. 报告中出现的任何统计数字，必须由脚本生成到文件，报告只引用文件路径与内容。
4. 不得为了让测试通过而修改测试断言或删除测试，确需修改时单独列出理由。
5. 前端完成的页面必须附三个断点的截图（手机 390、平板 820、桌面 1440）。

---

## 2. 技术栈

版本号为编写时的基线，以实际锁文件为准。

### 2.1 后端

| 用途 | 选型 | 说明 |
|---|---|---|
| 语言 | Python 3.12 | |
| 包管理 | uv | Windows 与 Linux 一致 |
| Web 框架 | FastAPI + Uvicorn | SSE 用于进度与流式对话 |
| ORM | SQLAlchemy 2.x（同步即可） | SQLite 单文件，WAL 模式 |
| 数据校验 | Pydantic v2 | 模型输出一律先过 Pydantic |
| 迁移 | Alembic | |
| PDF 渲染与文本坐标 | PyMuPDF | 渲染页图、提取字符级坐标 |
| OCR | RapidOCR（onnxruntime 后端） | 纯 CPU，x86 与 arm64 均有 wheel；模型文件预置到仓库外的 models 目录 |
| 图片 | Pillow + pillow-heif | 支持 iPhone HEIC |
| 全文检索 | SQLite FTS5（trigram 分词器） | 少于 3 个字的查询回退为 LIKE |
| PPT | python-pptx | |
| PPT 渲染为图片 | LibreOffice headless（可选） | 用于视觉核验，缺失时跳过该步骤 |
| 加密 | cryptography（Fernet） | 映射表与 API Key |
| 定时任务 | APScheduler | 提醒生成 |
| 日历 | icalendar | ICS 订阅 |
| HTTP 客户端 | httpx | 下载条款文档 |
| 模型 SDK | 火山方舟官方 Python SDK（Ark 客户端）+ openai SDK | 前者用于方舟 Responses API，后者用于其他 OpenAI 兼容模型 |
| 测试 | pytest + pytest-asyncio + respx | |

### 2.2 前端

| 用途 | 选型 | 说明 |
|---|---|---|
| 框架 | Vue 3 + TypeScript + Vite | |
| 状态 | Pinia | |
| 路由 | Vue Router，路由切换使用 View Transitions API | 浏览器不支持时直接切换 |
| 无样式组件 | Reka UI | 提供弹层、对话框、选择器的可访问性行为，样式全部自写 |
| 样式 | 原生 CSS + CSS 自定义属性 + CSS 嵌套 | 不使用 Tailwind 与组件库皮肤 |
| 图表 | ECharts（vue-echarts，按需引入） | 雷达图、瀑布图、热力图 |
| 时间轴 | 自研 SVG 组件 | |
| 图标 | lucide-vue-next | 打包进产物 |
| 动效 | CSS 过渡 + Web Animations API | 不引入大型动画库 |
| 3D（P2） | TresJS（Three.js 的 Vue 封装） | 按路由懒加载 |
| 字体 | HarmonyOS Sans SC（界面）+ 思源宋体 Source Han Serif SC（原文引用） | 本地 woff2，只保留需要的字重 |
| 端到端测试 | Playwright | 含三断点截图 |

---

## 3. Windows 11 开发环境

### 3.1 安装基础工具

在 PowerShell（管理员）中执行：

```powershell
winget install --id Git.Git -e
winget install --id astral-sh.uv -e
winget install --id OpenJS.NodeJS.LTS -e
corepack enable
corepack prepare pnpm@latest --activate

# 可选：PPT 视觉核验需要
winget install --id TheDocumentFoundation.LibreOffice -e

# 可选：本地验证 Docker 镜像
winget install --id Docker.DockerDesktop -e
```

开启长路径支持，避免 node_modules 路径超长：

```powershell
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
git config --global core.longpaths true
```

### 3.2 初始化与启动

```powershell
git clone <repo> policybook
cd policybook

# 后端
cd backend
uv sync
Copy-Item ..\.env.example ..\.env
uv run python -m app.scripts.init      # 建库、生成密钥、下载 OCR 模型到 ..\models
uv run uvicorn app.main:app --reload --port 8000

# 前端（新开一个终端）
cd frontend
pnpm install
pnpm dev                                # 默认 5173，/api 代理到 8000
```

`scripts/dev.ps1` 负责同时拉起前后端，供日常使用。

### 3.3 Windows 注意事项

| 问题 | 处理 |
|---|---|
| 换行符 | 仓库根放 `.gitattributes`，内容 `* text=auto eol=lf`，`*.ps1 text eol=crlf` |
| 路径 | 后端一律使用 `pathlib.Path`，禁止手写 `/` 或 `\\` 拼接 |
| 文件名编码 | 上传文件落盘时按哈希命名，原始文件名只存数据库 |
| 脚本执行策略 | 若 `dev.ps1` 无法执行：`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| 端口占用 | `.env` 中可改 `APP_PORT` 与前端代理目标 |
| LibreOffice 路径 | `.env` 中设置 `SOFFICE_PATH`，默认探测 `C:\Program Files\LibreOffice\program\soffice.exe` |
| 杀毒软件拦截 OCR 模型下载 | 手动下载后放入 `models/rapidocr/` |

### 3.4 环境变量

```dotenv
# 服务
APP_HOST=0.0.0.0
APP_PORT=8000
DATA_DIR=./data
MODELS_DIR=./models
APP_SECRET=                    # init 脚本自动生成，用于加密
FAMILY_PASSWORD=               # 首次启动时在界面设置后写入数据库，此处可留空

# 模型（界面中也可配置，环境变量作为初始值）
ARK_API_KEY=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
MODEL_PRIMARY=doubao-seed-evolving
MODEL_BASELINE=doubao-seed-2-1-pro-260628

# 可选
SOFFICE_PATH=
HTTP_PROXY=
EVAL_MODE=false
```

Agent Plan 与按量付费的 Base URL、模型 ID 可能不同，以方舟控制台显示为准，写入 `config/models.yaml`。

---

## 4. 仓库结构

```
policybook/
├── AGENTS.md
├── CLAUDE.md
├── .env.example
├── .gitattributes
├── docker/
│   ├── Dockerfile
│   └── compose.yaml
├── config/
│   ├── models.yaml                 # 模型端点列表
│   ├── domains.yaml                # 续保检索白名单
│   └── gaps/
│       └── accident.yaml           # 意外险缺口清单
├── docs/
│   ├── PRD.md
│   └── DEV-GUIDE.md
├── scripts/
│   ├── dev.ps1
│   └── dev.sh
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   ├── app/
│   │   ├── main.py
│   │   ├── settings.py
│   │   ├── db/                     # engine、models、repositories
│   │   ├── api/                    # 路由，按资源拆文件
│   │   ├── schemas/                # API 请求响应模型
│   │   ├── jobs/                   # 持久化任务队列与各步骤处理器
│   │   ├── ingest/
│   │   │   ├── render.py           # PDF 与图片转页图、文本层
│   │   │   ├── ocr.py
│   │   │   ├── pii.py              # 脱敏
│   │   │   ├── extract.py          # 调用模型抽取
│   │   │   └── verify.py           # 引用校验与坐标回算
│   │   ├── llm/
│   │   │   ├── base.py             # Provider 接口
│   │   │   ├── ark.py
│   │   │   ├── openai_compat.py
│   │   │   ├── logging.py          # 调用日志
│   │   │   ├── schemas/            # 模型输出的 Pydantic 模型
│   │   │   └── prompts/            # 提示词模板（.md）
│   │   ├── qa/                     # 检索与问答
│   │   ├── claim/
│   │   │   ├── engine.py           # 纯函数计算引擎
│   │   │   └── service.py
│   │   ├── renewal/
│   │   │   ├── state_machine.py
│   │   │   ├── tools.py            # 暴露给模型的函数工具
│   │   │   ├── fetch.py            # 安全下载
│   │   │   └── compare.py
│   │   ├── coverage/               # 雷达与缺口计算
│   │   ├── reports/                # PPT 生成与核验
│   │   ├── reminders/
│   │   ├── eval/                   # 测评 CLI、判定器、故障注入
│   │   ├── utils/
│   │   │   ├── cn_money.py         # 中文金额解析
│   │   │   ├── cn_date.py
│   │   │   └── text_norm.py
│   │   └── scripts/
│   └── tests/
│       ├── fixtures/               # 公开条款 PDF 与合成保单，不含真实家庭数据
│       └── ...
├── frontend/
│   ├── index.html
│   ├── public/fonts/
│   ├── src/
│   │   ├── main.ts
│   │   ├── router.ts
│   │   ├── api/                    # 类型化请求封装、SSE 客户端
│   │   ├── stores/
│   │   ├── styles/
│   │   │   ├── tokens.css
│   │   │   ├── base.css
│   │   │   ├── glass.css
│   │   │   └── motion.css
│   │   ├── components/
│   │   │   ├── shell/              # 导航、背景、主题切换
│   │   │   ├── doc-viewer/         # 原文阅读器与高亮层
│   │   │   ├── timeline/
│   │   │   ├── charts/
│   │   │   ├── chat/
│   │   │   └── common/
│   │   └── pages/
│   └── tests/e2e/
├── eval/
│   ├── tasks/                      # 任务集（公开部分）
│   ├── private/                    # 家庭保单标注，加入 .gitignore
│   └── runs/                       # 跑批输出，加入 .gitignore
└── data/                           # 运行数据，加入 .gitignore
```

---

## 5. 后端设计

### 5.1 数据模型

主键统一使用 ULID 字符串；时间统一存 UTC ISO8601，展示时按 Asia/Shanghai 转换；金额统一存整数分。

| 表 | 关键字段 | 说明 |
|---|---|---|
| member | id, display_name, relation, birth_year, gender, occupation, city, social_insurance, color, real_name_enc, placeholder | real_name_enc 为加密值 |
| document | id, sha256, original_name, mime, page_count, source(upload/renewal), created_at | 一次上传一个 document；多张照片合并为一个 |
| page | id, document_id, page_no, image_path, masked_image_path, text_raw_enc, text_masked, char_map_path, is_ocr, pii_status | char_map 存字符坐标 JSON 文件路径 |
| pii_mapping | id, document_id, placeholder, kind, value_enc | |
| policy | id, document_id, insurer, product_name, policy_no_enc, category, subcategory, term_type, premium_cents, pay_mode, pay_years, sum_insured_cents, apply_date, effective_date, expiry_date, cooling_days, waiting_days, guaranteed_renewal, renewal_years, status, confirmed_at | |
| policy_party | id, policy_id, member_id, role(applicant/insured/beneficiary), share | |
| coverage | id, policy_id, parent_coverage_id, name, kind, limit_cents, deductible_cents, deductible_scope(annual/per_claim/none/unknown), ratio_with_si, ratio_without_si, waiting_days, is_rider | 比例存千分比整数 |
| clause | id, document_id, page_no, clause_no, title, category(liability/exclusion/definition/waiting/renewal/other), text_masked | 用于检索 |
| evidence | id, owner_type, owner_id, field, page_id, quote, start, end, rects_json, status(verified/unverified/not_found/conflict), model_value, human_value | 所有字段与责任项的出处 |
| job | id, kind, status, step, payload_json, progress, error, attempts, created_at, updated_at | 持久化任务 |
| chat_session | id, kind(qa/renewal), scope_json, state, profile_json, created_at | |
| chat_message | id, session_id, role, content, structured_json, created_at | |
| citation | id, message_id, evidence_like_json, status | |
| claim_run | id, member_id, input_json, facts_json, result_json, created_at | |
| tool_call | id, session_id, llm_call_id, name, args_json, result_digest, ok, injected_fault, created_at | |
| source_record | id, session_id, url, domain, title, retrieved_at, via(search/fetch), http_status, sha256 | URL 溯源依据 |
| llm_call | id, task_kind, model_id, provider, input_tokens, cached_tokens, output_tokens, reasoning_tokens, latency_ms, ok, error, request_digest, response_path, verify_summary_json, created_at | |
| reminder | id, policy_id, kind, due_date, status | |
| setting | key, value_json | 含加密的 API Key、参考保额、社保报销区间 |

`clause_fts` 为 FTS5 虚拟表：`CREATE VIRTUAL TABLE clause_fts USING fts5(text_masked, title, content='clause', content_rowid='rowid', tokenize='trigram');`

### 5.2 持久化任务队列

不引入 Redis 与 Celery。进程内一个 asyncio worker 轮询 `job` 表，按步骤执行，每步完成立即写回 `step` 与 `progress`。服务启动时把 `running` 状态的任务重置为 `queued`，从最后完成的步骤继续。解析任务的步骤与 PRD 3.3 表格一一对应，每一步是一个独立函数，输入输出落库或落盘，便于单步重跑与单元测试。

阻塞型操作（PyMuPDF 渲染、OCR、LibreOffice）使用 `asyncio.to_thread` 或进程池，OCR 并发默认 1，可配置。

### 5.3 API 契约

统一前缀 `/api`；错误响应 `{"error": {"code": "...", "message": "..."}}`；列表接口支持 `?cursor=&limit=`。

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | /auth/login | 家庭密码登录，返回 HttpOnly Cookie |
| GET/POST/PATCH/DELETE | /members, /members/{id} | 成员管理 |
| POST | /imports | multipart 上传，返回 job 列表 |
| GET | /jobs/{id} | 任务状态 |
| GET | /jobs/{id}/events | SSE：step、progress、error、done |
| GET | /documents/{id}/pages/{n}/image?masked=0\|1 | 页图 |
| GET | /documents/{id}/pages/{n}/masked-text | 发送给模型的文本预览 |
| GET | /imports/{jobId}/review | 核对数据：字段、责任项、证据与状态 |
| PATCH | /imports/{jobId}/review/fields/{field} | 人工修改字段 |
| POST | /imports/{jobId}/confirm | 确认入库 |
| GET | /policies | 筛选与搜索 |
| GET | /policies/{id} | 详情，含责任项、免责、证据 |
| DELETE | /policies/{id} | 删除（连带文件） |
| GET | /overview | 家庭总览数据：时间轴区段、关键数字、待办 |
| POST | /qa/sessions | 创建问答会话，body 含 scope |
| POST | /qa/sessions/{id}/messages | 提问，SSE 返回流式文本与最终结构化结果 |
| POST | /claims/simulate | 理赔模拟，返回 facts、steps、result |
| POST | /renewal/sessions | 创建续保会话，body 含 policy_id |
| POST | /renewal/sessions/{id}/messages | 用户回复，SSE 返回状态变化、追问、进度、报告 |
| GET | /renewal/sessions/{id}/report | 报告 |
| GET | /coverage/radar?member_ids= | 雷达数据 |
| GET | /coverage/heatmap | 热力图数据 |
| POST | /reports/ppt | 生成 PPT，返回 job |
| POST | /reports/ppt/{id}/revise | 自然语言修改 |
| GET | /reports/ppt/{id} | 下载与核验结果 |
| GET | /calendar/{token}.ics | 日历订阅，token 在设置页生成 |
| GET/PUT | /settings | 设置 |
| POST | /settings/models/test | 模型连通测试 |
| GET | /eval/summary | 测评看板 |
| GET | /llm-calls | 调用日志 |

Pydantic 模型定义在 `backend/app/schemas/`；前端类型由 FastAPI 的 OpenAPI 生成（`pnpm gen:api`，使用 openapi-typescript），禁止手写重复类型。

### 5.4 SSE 事件格式

```text
event: step
data: {"job_id":"01J...","step":"pii","progress":0.35}

event: token
data: {"text":"根据"}

event: result
data: {...结构化结果...}

event: error
data: {"code":"MODEL_TIMEOUT","message":"模型响应超时，已保存进度，可重试"}

event: done
data: {}
```

`done` 与 `error` 为终止事件，前端收到后关闭连接，不自动重连。

---

## 6. 模型接入层与提示词

### 6.1 Provider 接口

```python
class LLMProvider(Protocol):
    name: str
    model_id: str

    async def respond(
        self,
        *,
        task_kind: str,
        instructions: str,
        inputs: list[InputItem],          # TextItem | ImageItem(png bytes) | FileItem
        tools: list[ToolSpec] | None = None,
        output_schema: type[BaseModel] | None = None,
        max_output_tokens: int = 8000,
        stream: bool = False,
    ) -> LLMResult: ...
```

`LLMResult` 包含 `text`、`parsed`（通过 output_schema 校验后的对象）、`tool_calls`、`usage`（input/cached/output/reasoning）、`raw_path`（原始响应落盘路径）。

实现要求：

1. `ark.py` 基于火山方舟 Responses API（`/api/v3/responses`）。图片输入、函数调用、联网搜索工具、结构化输出的具体参数名，开发时以方舟文档「图片理解」「Function Calling」「Web Search」「文档理解」各章节的最新示例为准，不要凭记忆编写。
2. `openai_compat.py` 基于 Chat Completions，用于其他模型；处理全部 `tool_calls`，工具结果以 `role=tool` 与 `tool_call_id` 回填。
3. 结构化输出：接口支持 JSON Schema 约束时启用；否则在提示词中给出 schema，拿到结果后用 Pydantic 校验，失败时把校验错误回传做一次修复请求，仍失败则任务步骤标记失败。
4. 每次调用都经过 `llm/logging.py` 写入 `llm_call` 表，原始请求与响应（已脱敏内容）落盘到 `data/llm_raw/`。
5. 超时、限流按指数退避重试，最多 3 次；重试次数记入日志。
6. 同一 Provider 实例内复用 HTTP 连接；并发上限可配置，默认 2。

### 6.2 模型配置文件

```yaml
# config/models.yaml
default: evolving
models:
  evolving:
    provider: ark
    base_url: https://ark.cn-beijing.volces.com/api/v3
    model_id: doubao-seed-evolving
    api_key_env: ARK_API_KEY
    display_name: Seed-2.1-pro-0915
    supports: [image, tools, web_search]
  pro_0628:
    provider: ark
    base_url: https://ark.cn-beijing.volces.com/api/v3
    model_id: doubao-seed-2-1-pro-260628
    api_key_env: ARK_API_KEY
    display_name: Seed-2.1-pro-0628
    supports: [image, tools, web_search]
```

### 6.3 提示词模板

提示词存放在 `backend/app/llm/prompts/*.md`，使用 Jinja2 渲染。每个模板顶部写明版本号，修改后版本号加一，版本号记入 `llm_call`。

| 模板 | 任务 | 输出模型 |
|---|---|---|
| classify_pages.md | 页面类型判定 | PageTypes |
| extract_policy.md | 字段抽取 | PolicyExtraction |
| extract_coverages.md | 责任项与免责抽取 | CoverageExtraction |
| qa_answer.md | 条款问答 | QAAnswer |
| claim_facts.md | 理赔事实与责任项匹配 | ClaimFacts |
| renewal_agent.md | 续保会话主提示词 | 工具调用驱动 |
| renewal_report.md | 差异说明文字 | RenewalNarrative |
| ppt_summary.md | 每页摘要 | SlideSummaries |
| ppt_visual_check.md | PPT 截图检查 | VisualIssues |

所有模板共用的约束段落：

```text
你处理的是经过脱敏的保险合同。〔成员A〕〔证件1〕这类方括号占位符代表被隐藏的个人信息，原样保留，不要猜测其真实内容。

引用规则：
1. quote 必须从给定页面文本中逐字复制，包括标点，不得改写、概括或拼接不相邻的句子。
2. 单条 quote 不超过 200 字。
3. 找不到依据时，字段值填 null，quote 填 null，不要编造。

输出只包含符合 schema 的 JSON。
```

### 6.4 关键输出模型（节选）

```python
class Evidence(BaseModel):
    page: int
    quote: str | None

class FieldValue(BaseModel):
    value: str | None
    evidence: Evidence | None

class PolicyExtraction(BaseModel):
    insurer: FieldValue
    product_name: FieldValue
    category: Literal["critical_illness","medical","accident","term_life","whole_life",
                      "annuity","endowment_whole_life","property","auto","other"]
    subcategory: FieldValue
    applicant: FieldValue            # 占位符
    insureds: list[FieldValue]
    beneficiaries: list[FieldValue]
    sum_insured: FieldValue          # 原文金额字符串，由代码解析
    premium: FieldValue
    pay_mode: FieldValue
    pay_years: FieldValue
    apply_date: FieldValue
    effective_date: FieldValue
    expiry_date: FieldValue
    cooling_days: FieldValue
    waiting_days: FieldValue
    guaranteed_renewal: FieldValue

class CoverageItem(BaseModel):
    name: str
    kind: Literal["death","disability","critical_illness","medical","accident_medical",
                  "hospital_allowance","transport_extra","sudden_death","other"]
    limit: FieldValue
    deductible: FieldValue
    deductible_scope: Literal["annual","per_claim","none","unknown"]
    ratio_with_si: FieldValue
    ratio_without_si: FieldValue
    waiting_days: FieldValue
    conditions: list[Evidence]
    is_rider: bool

class Exclusion(BaseModel):
    evidence: Evidence
    plain_explanation: str           # 通俗解释，不超过 80 字

class QAAnswer(BaseModel):
    verdict: Literal["likely_covered","likely_not_covered","depends","no_basis"]
    reasoning: list[str]
    citations: list[CitationRef]     # document_id + page + quote
    confirm_with_insurer: list[str]
```

金额、日期、比例一律让模型返回原文字符串，由 `utils/cn_money.py` 等模块解析，避免模型做单位换算。

### 6.5 续保 Agent 的工具

| 工具 | 参数 | 实现要点 |
|---|---|---|
| get_baseline | 无 | 返回当前保单的责任项摘要 |
| ask_user | questions: [{dimension, question, why, options[]}]，最多 2 条 | 调用后结束本轮，等待用户回复 |
| update_profile | dimension, value, source_message_id | 写入需求画像 |
| search_web | query | 后端代理执行；结果按 `config/domains.yaml` 过滤；每条结果写入 source_record；测评模式下可注入故障 |
| fetch_document | url | 只允许白名单域名与 http/https；拒绝解析到内网与保留地址的主机（防 SSRF）；限制 30MB 与 PDF/HTML；下载后走解析流程并返回 document_id |
| get_candidate_coverages | document_id | 返回已校验的责任项 |
| finish_report | narrative 字段 | 触发代码生成对比矩阵并合并模型撰写的说明 |

`search_web` 的后端实现通过 `SearchProvider` 接口隔离，默认实现为向方舟发起一次开启联网搜索工具的子请求并解析其返回的来源；接口预留自建搜索服务的实现位。故障注入在 `SearchProvider` 外层包装，不改动 Agent 代码。

---

## 7. 前端设计系统

### 7.1 设计构想

**主题：纸本与护面玻璃。** 保单是纸，玻璃是护在纸上的一层保护。界面由三层构成：最底层是缓慢流动的晨雾色环境光；中间层是半透明磨玻璃面板，承载导航、表单、图表等「系统理解」的内容；最上层是原文页面，保持纸张般不透明、清晰、无模糊。玻璃与纸的材质差异本身就在表达信息：玻璃上是系统整理出来的，纸上是合同原文。

**字体承担同样的分工。** 界面文字、数字、模型的解释用无衬线体 HarmonyOS Sans SC；凡是合同原文引用，一律用思源宋体，并带左侧细竖线。用户不需要读说明，就能分辨哪句是原文、哪句是解读。

**颜色语义固定。** 青瓷色只表示「已核验 / 有依据」，杏黄只表示「待确认 / 等待期」，朱砂只表示「缺口 / 冲突 / 免责」，暮紫只表示「模型生成内容」。装饰性用色只出现在背景环境光中。

**一个标志性时刻。** 点击任意引用时，原文阅读器滚动到对应页，高亮框从引用卡片的位置出发，以一次柔和的光晕展开并停留在原文上。全站其他动效都保持克制。

### 7.2 与常见模板的差异自查

编写时对照了当前生成式页面最常见的做法，做了以下调整：

| 常见做法 | 本项目的处理 |
|---|---|
| 所有内容切成等大圆角卡片，统一灰色阴影 | 圆角分三级（面板 22px、控件 12px、标签全圆），阴影带背景色相，不同层级阴影强度不同 |
| 渐变色块作为装饰铺满卡片 | 渐变只存在于最底层环境光，面板本身不加渐变 |
| 大数字 + 小标签的统计卡作为首页主视觉 | 首页主视觉是全家保障时间轴，数字退居右侧窄栏 |
| 每个区块进场都淡入上滑 | 页面加载只有时间轴色带绘制一次，其余内容直接出现 |
| 标题上方的全大写小标签、中点分隔的元信息串 | 不使用；元信息用表格或并列字段表达 |
| 小号数据标签使用等宽字体 | 数字统一使用 HarmonyOS Sans SC 的等宽数字特性 `font-variant-numeric: tabular-nums` |

### 7.3 色板

| 名称 | 浅色主题 | 深色主题 | 用途 |
|---|---|---|---|
| 雾白 mist | #EEF2F6 | — | 浅色背景基底 |
| 深潭 pool | #14233A | #0E1A2B | 浅色主文字 / 深色背景基底 |
| 青瓷 celadon | #2A8F82 | #4FC2B2 | 已核验、主操作 |
| 杏黄 apricot | #C98217 | #F0B452 | 待确认、等待期 |
| 朱砂 cinnabar | #C8443B | #F07A70 | 缺口、冲突、免责 |
| 暮紫 dusk | #5E54C9 | #9C94F2 | 模型生成内容标记 |
| 纸 paper | #FFFDF8 | #F7F5EF（阅读器内保持浅色纸面） | 原文页面底色 |

浅色主题的状态色为满足玻璃面板上的文字对比度已适当压暗；实际使用前用对比度工具在最终背景上复核，要求正文 4.5:1、大字 3:1。

### 7.4 设计令牌

```css
/* frontend/src/styles/tokens.css */
@font-face {
  font-family: "HarmonyOS Sans SC";
  src: url("/fonts/HarmonyOS_Sans_SC_Regular.woff2") format("woff2");
  font-weight: 400; font-display: swap;
}
@font-face {
  font-family: "HarmonyOS Sans SC";
  src: url("/fonts/HarmonyOS_Sans_SC_Medium.woff2") format("woff2");
  font-weight: 500; font-display: swap;
}
@font-face {
  font-family: "HarmonyOS Sans SC";
  src: url("/fonts/HarmonyOS_Sans_SC_Bold.woff2") format("woff2");
  font-weight: 700; font-display: swap;
}
@font-face {
  font-family: "Source Han Serif SC";
  src: url("/fonts/SourceHanSerifSC-Regular.woff2") format("woff2");
  font-weight: 400; font-display: swap;
}

:root {
  color-scheme: light;

  /* 基础色 */
  --c-mist: #EEF2F6;
  --c-pool: #14233A;
  --c-celadon: #2A8F82;
  --c-apricot: #C98217;
  --c-cinnabar: #C8443B;
  --c-dusk: #5E54C9;
  --c-paper: #FFFDF8;

  /* 语义色 */
  --bg: var(--c-mist);
  --text: var(--c-pool);
  --text-muted: color-mix(in oklch, var(--c-pool) 62%, var(--c-mist));
  --ok: var(--c-celadon);
  --pending: var(--c-apricot);
  --risk: var(--c-cinnabar);
  --ai: var(--c-dusk);

  /* 玻璃 */
  --glass-fill: color-mix(in oklch, white 58%, transparent);
  --glass-fill-strong: color-mix(in oklch, white 76%, transparent);
  --glass-stroke: color-mix(in oklch, white 70%, transparent);
  --glass-edge: inset 0 1px 0 color-mix(in oklch, white 85%, transparent);
  --glass-blur: 18px;
  --glass-shadow:
    0 1px 2px color-mix(in oklch, var(--c-pool) 8%, transparent),
    0 12px 32px -12px color-mix(in oklch, var(--c-pool) 22%, transparent);

  /* 环境光 */
  --aura-1: #9FD8CF;
  --aura-2: #B9C6F2;
  --aura-3: #F4D9B0;

  /* 字体 */
  --font-ui: "HarmonyOS Sans SC", system-ui, "PingFang SC", "Microsoft YaHei UI", sans-serif;
  --font-quote: "Source Han Serif SC", "Songti SC", "SimSun", serif;

  /* 字号：以 16px 为基准的 1.2 比例，中文界面不宜跨度过大 */
  --fs-12: 0.75rem;
  --fs-14: 0.875rem;
  --fs-16: 1rem;
  --fs-19: 1.1875rem;
  --fs-23: 1.4375rem;
  --fs-28: 1.75rem;
  --fs-34: 2.125rem;
  --lh-ui: 1.6;
  --lh-quote: 1.85;

  /* 间距：4 的倍数 */
  --sp-1: 4px; --sp-2: 8px; --sp-3: 12px; --sp-4: 16px;
  --sp-5: 24px; --sp-6: 32px; --sp-7: 48px; --sp-8: 64px;

  /* 圆角分级 */
  --r-panel: 22px;
  --r-control: 12px;
  --r-pill: 999px;
  --r-page: 6px;

  /* 动效 */
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --ease-inout: cubic-bezier(0.65, 0, 0.35, 1);
  --dur-fast: 140ms;
  --dur-base: 220ms;
  --dur-slow: 480ms;
}

:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #0E1A2B;
  --text: #E6ECF3;
  --text-muted: color-mix(in oklch, #E6ECF3 62%, #0E1A2B);
  --ok: #4FC2B2;
  --pending: #F0B452;
  --risk: #F07A70;
  --ai: #9C94F2;
  --glass-fill: color-mix(in oklch, #1B2B42 55%, transparent);
  --glass-fill-strong: color-mix(in oklch, #1B2B42 78%, transparent);
  --glass-stroke: color-mix(in oklch, white 12%, transparent);
  --glass-edge: inset 0 1px 0 color-mix(in oklch, white 10%, transparent);
  --glass-shadow:
    0 1px 2px rgb(0 0 0 / 0.3),
    0 16px 40px -16px rgb(0 0 0 / 0.55);
  --aura-1: #1F5C58;
  --aura-2: #2E3A75;
  --aura-3: #5A4323;
}
```

主题默认跟随系统设置；用户手动切换后，偏好保存在浏览器 `localStorage` 中（本项目是独立部署的网页应用，可正常使用浏览器存储），同时写入服务端设置，便于家庭成员在不同设备上保持一致。

### 7.5 玻璃与环境光实现

```css
/* frontend/src/styles/glass.css */
.glass {
  background: var(--glass-fill);
  border: 1px solid var(--glass-stroke);
  box-shadow: var(--glass-edge), var(--glass-shadow);
  border-radius: var(--r-panel);
  -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(140%);
  backdrop-filter: blur(var(--glass-blur)) saturate(140%);
}
.glass--strong { background: var(--glass-fill-strong); }

@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
  .glass { background: var(--glass-fill-strong); }
}

/* 简洁模式：关闭模糊与环境光动画 */
:root[data-lite="true"] .glass {
  -webkit-backdrop-filter: none;
  backdrop-filter: none;
  background: var(--glass-fill-strong);
}

/* 环境光：固定在视口底层的三团模糊色斑，40 秒缓慢漂移 */
.aura {
  position: fixed; inset: 0; z-index: -1; overflow: hidden;
  background: var(--bg);
}
.aura::before, .aura::after, .aura > i {
  content: ""; position: absolute; border-radius: 50%;
  filter: blur(80px); opacity: 0.55;
  will-change: transform;
}
.aura::before { width: 52vmax; height: 52vmax; background: var(--aura-1); top: -18vmax; left: -12vmax; animation: drift-a 40s var(--ease-inout) infinite alternate; }
.aura::after  { width: 46vmax; height: 46vmax; background: var(--aura-2); bottom: -20vmax; right: -10vmax; animation: drift-b 46s var(--ease-inout) infinite alternate; }
.aura > i     { width: 30vmax; height: 30vmax; background: var(--aura-3); top: 40%; left: 45%; animation: drift-c 52s var(--ease-inout) infinite alternate; }

@keyframes drift-a { to { transform: translate(8vmax, 6vmax) scale(1.08); } }
@keyframes drift-b { to { transform: translate(-6vmax, -8vmax) scale(0.94); } }
@keyframes drift-c { to { transform: translate(-10vmax, 4vmax) scale(1.12); } }

/* 叠加极细噪点，避免大面积渐变出现色带 */
.aura { background-image: url("/textures/noise-128.png"); background-blend-mode: soft-light; }

@media (prefers-reduced-motion: reduce) {
  .aura::before, .aura::after, .aura > i { animation: none; }
}
:root[data-lite="true"] .aura::before,
:root[data-lite="true"] .aura::after,
:root[data-lite="true"] .aura > i { display: none; }
```

性能规则：

1. 同一屏幕内带 `backdrop-filter` 的元素最多 3 个大面板；列表项、表格行、按钮不加模糊，改用 `--glass-fill-strong` 实色半透明。
2. 滚动容器内部不放玻璃元素，玻璃只用于固定位置的导航与面板外框。
3. 首次加载时检测 `navigator.hardwareConcurrency <= 4` 或设备内存较小时默认开启简洁模式，用户可在设置中改回。

### 7.6 布局

**桌面（≥1440px）**

```
┌────────┬──────────────────────────────────────┬─────────────────┐
│ 导航栏 │  页面主内容                          │  原文阅读器     │
│ 玻璃   │  （玻璃面板，最大宽度 960px，左对齐）│  （纸面，可收起）│
│ 76px   │                                      │  440px          │
└────────┴──────────────────────────────────────┴─────────────────┘
```

**笔记本与平板横屏（1024–1439px）**：导航收为图标栏，原文阅读器改为从右侧滑出的抽屉，覆盖主内容右侧。

**平板竖屏（600–1023px）**：导航移到顶部，主内容单栏，阅读器为右侧全高抽屉。

**手机（<600px）**：底部导航（总览、保单、问答、模拟、更多）；阅读器为全屏底部抽屉，支持下滑关闭；表格改为分组列表。

文本对齐：正文与表单一律左对齐；数字列右对齐；原文引用块两端不对齐（中文两端对齐在窄屏易出现大字距）。正文最大行宽约 38 个汉字。

### 7.7 家庭总览页结构

```
┌──────────────────────────────────────────────────────────┬──────────────┐
│ 家里的保障状况                                           │ 年保费合计   │
│                                                          │ 生效保单     │
│ ┌──────────────────────────────────────────────────────┐ │ 30天内到期   │
│ │ 时间轴  2025.03 ────────── 今天 ────────── 2027.03   │ │ 有空档的成员 │
│ │ 本人    ███████████▒▒▒▒████████████                   │ ├──────────────┤
│ │ 配偶    ░░░████████████████████████████               │ │ 待处理       │
│ │ 父亲    ████████  ┆┆┆空档┆┆┆  ██████                  │ │ · 待核对 2   │
│ │ 孩子    ████████████████████████████████              │ │ · 即将到期 1 │
│ └──────────────────────────────────────────────────────┘ │              │
│  ░ 等待期  █ 生效  ┆ 空档                                 │              │
├──────────────────────────────────────────────────────────┴──────────────┤
│ 上传保单        问一个条款问题        估算一次理赔                      │
└─────────────────────────────────────────────────────────────────────────┘
```

时间轴色带颜色取成员头像色；色带悬停显示保单名与期间；点击进入保单详情。首次加载时色带自左向右绘制一次，时长 480ms，按成员错开 60ms。

### 7.8 原文阅读器与引用定位

| 元素 | 规范 |
|---|---|
| 页面 | 纸色底 `--c-paper`，圆角 `--r-page`，轻微投影；深色主题下仍保持浅色纸面，外围压暗 |
| 高亮框 | 由后端返回的 rects 绘制，1.5px 边框 + 12% 填充，颜色取字段状态色 |
| 引用卡片 | 思源宋体正文，左侧 2px 竖线，竖线颜色为状态色；卡片底部显示「第 N 页」 |
| 定位动效 | 1）阅读器平滑滚动到目标页（`scrollIntoView`，180ms 后开始下一步）；2）高亮框从引用卡片的屏幕坐标以 FLIP 方式移动并缩放到原文位置，480ms `--ease-out`；3）到位后外发光扩散一次并消退，600ms。减少动态效果时跳过 2 和 3，直接显示高亮框 |
| 缩放 | 适应宽度 / 100% / 150%，手机支持双指缩放 |
| 键盘 | `[` `]` 翻页，`Esc` 关闭抽屉 |

实现：页图由后端渲染为 144 DPI PNG，前端按容器宽度缩放；rects 使用 PDF 坐标（pt），前端按 `renderedWidth / pageWidthPt` 换算。不在前端引入 pdf.js，减少包体积与 NAS 负载。

### 7.9 组件规范摘要

| 组件 | 要点 |
|---|---|
| 按钮 | 主按钮青瓷实底白字；次按钮玻璃底；危险操作朱砂描边；文字写明动作结果，如「确认入库」「开始估算」 |
| 状态徽标 | 圆点 + 文字，不只用颜色表达：已核验、待确认、未找到、冲突 |
| 模型内容标记 | 模型生成的段落左上角带暮紫色小图标，悬停说明「由模型根据条款整理」 |
| 表单 | 标签在上；错误提示写明原因与修改方法，如「保费需要是数字，例如 1280」 |
| 空状态 | 说明下一步做什么，如保单库为空时显示上传区本身，而不是插画 |
| 对话流 | 用户消息靠右玻璃气泡；模型消息无气泡、全宽排版，引用卡片内嵌在段落之后 |
| 追问卡 | 续保顾问的追问以卡片形式出现，包含问题、一句「为什么问」、快捷选项按钮与自由输入 |
| 需求画像卡 | 续保页右侧固定，维度逐项点亮，未确认项灰色 |
| 瀑布图 | 总费用柱为深潭色，社保抵扣为青瓷浅色，各保单赔付为青瓷，自付为朱砂；每段可点击展开条款依据 |
| 雷达图 | 参考保额为虚线外圈；成员多边形使用成员头像色 20% 填充 |
| Toast | 与按钮动作同名，如「已确认入库」 |

### 7.10 动效规则

| 类型 | 允许 | 时长 |
|---|---|---|
| 路由切换 | View Transitions 交叉淡化 | 180ms |
| 抽屉、对话框 | 滑入与淡入 | 220ms |
| 列表增删 | 高度与透明度过渡 | 220ms |
| 首页时间轴 | 仅首次加载绘制 | 480ms |
| 引用定位 | 见 7.8 | 共约 1.2s |
| SSE 流式文字 | 直接追加，不做逐字动画 | — |
| 悬停 | 仅改变背景透明度或边框色，不做位移和缩放 | 140ms |

禁止：进场淡入上滑的滚动触发动画、卡片悬停上浮、数字滚动计数、无限循环的装饰动画（环境光除外）。

### 7.11 可访问性清单

1. 所有交互元素可键盘到达，焦点环为 2px 青瓷色外描边加 2px 偏移，在玻璃背景上清晰可见。
2. 图表提供等价的数据表视图切换。
3. 状态不单靠颜色，必须有文字或图标。
4. `prefers-reduced-motion` 与简洁模式都生效。
5. 页面语言 `lang="zh-CN"`，原文引用块加 `lang` 与 `cite` 语义。

---

## 8. 核心算法

### 8.1 页面渲染与字符坐标

```python
def render_pdf(path: Path, out_dir: Path) -> list[PageArtifact]:
    doc = fitz.open(path)
    for page in doc:
        pix = page.get_pixmap(dpi=144)
        pix.save(out_dir / f"p{page.number+1:03d}.png")
        raw = page.get_text("rawdict")
        chars = []          # [(char, x0, y0, x1, y1)]
        for block in raw["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    for ch in span["chars"]:
                        chars.append((ch["c"], *ch["bbox"]))
                chars.append(("\n", *line["bbox"]))
        ...
```

有效字符数（去掉空白与标点）少于 40 的页判定为扫描页，走 OCR。OCR 结果以「行文本 + 行框」保存，行内字符坐标按字符数均分近似。

### 8.2 文本归一化与引用校验

```python
def normalize_with_map(text: str) -> tuple[str, list[int]]:
    """返回归一化文本，以及每个归一化字符对应原文下标。
    规则：NFKC；删除所有空白；全角半角标点统一；去掉 PDF 断行产生的连字符。"""

def verify_quote(page_text: str, quote: str) -> Match | None:
    norm_page, idx_map = normalize_with_map(page_text)
    norm_quote, _ = normalize_with_map(quote)
    if len(norm_quote) < 4:
        return None                      # 过短引用不接受
    hits = find_all(norm_page, norm_quote)
    if not hits:
        return None
    start = idx_map[hits[0]]
    end = idx_map[hits[0] + len(norm_quote) - 1] + 1
    return Match(start=start, end=end, ambiguous=len(hits) > 1)
```

校验顺序：先在模型给出的页码上查找；找不到时在同一文档全部页上查找，命中则更正页码并记录 `page_corrected=true`；仍找不到则状态为 `not_found`。坐标由 `start..end` 对应的字符框按行合并得到矩形列表。

### 8.3 中文金额与比例解析

`utils/cn_money.py` 需覆盖：`50万元`、`伍拾万元整`、`500,000.00元`、`人民币 50 万`、`0元`、`1万元/年`、`首年保费 1,280 元`。返回 `Decimal` 与单位（元、万元），存储时转为分。比例解析覆盖 `100%`、`百分之八十`、`80%（经社保）`。每种写法至少一条单元测试。

数值一致性：字段值从其 quote 中重新解析，与模型给出的 value 解析结果不一致时，状态置为 `conflict`。

### 8.4 脱敏

```python
ID_RE = re.compile(r"(?<![0-9A-Za-z])[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx](?![0-9A-Za-z])")
PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
CARD_RE = re.compile(r"(?<!\d)\d{16,19}(?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
```

1. 身份证号必须通过 GB 11643 校验位计算才判定命中。
2. 银行卡号通过 Luhn 校验，且前后 20 字内出现「账号」「卡号」「银行」「账户」之一才命中，避免误伤保单号与金额。
3. 成员真实姓名做精确匹配，按姓名长度倒序替换，避免「张伟」先于「张伟明」被替换。
4. 替换在原文上执行，同时记录每处替换的字符区间，用于在页图上按字符坐标打实心色块。
5. 同一值在同一文档内使用同一占位符。
6. 每页脱敏后再跑一遍全部正则，仍有命中则 `pii_status=failed`，该页不发送给模型。
7. 单元测试必须包含：合法与非法校验位的身份证、与卡号等长的保单号、带空格分组的手机号。

### 8.5 理赔计算引擎

`claim/engine.py` 是纯函数模块，不访问数据库和模型，全部使用 `Decimal`，结果为区间 `(low, high)`。

```python
@dataclass
class ClaimInput:
    event_date: date
    event_kind: Literal["illness", "accident", "death", "other"]
    total_cost: Decimal
    si_covered_cost: Decimal | None      # 社保范围内费用
    si_reimbursed: Decimal | None        # 用户填写的实际社保报销
    si_ratio_range: tuple[Decimal, Decimal] | None
    matched: list[MatchedCoverage]       # 由模型匹配、代码补全参数

@dataclass
class Step:
    label: str
    amount: tuple[Decimal, Decimal]
    remaining: tuple[Decimal, Decimal]
    coverage_id: str | None
    evidence_ids: list[str]
    note: str | None

def simulate(inp: ClaimInput) -> ClaimResult:
    remaining = (inp.total_cost, inp.total_cost)
    steps = []

    # 1. 社保
    si = social_insurance_range(inp)
    remaining = sub(remaining, si)
    steps.append(Step("社保报销", si, remaining, None, [], si_note(inp)))

    # 2. 等待期过滤
    active, excluded = split_by_waiting_period(inp.matched, inp.event_date)

    # 3. 补偿型：按 小额医疗 → 意外医疗 → 百万医疗 → 其他 顺序
    for cov in order_indemnity(active):
        base = apply_deductible(remaining, cov)            # 区间运算，免赔额共享规则未知时取两端
        paid = mul(base, ratio_range(cov, inp))            # 经社保与未经社保两档
        paid = cap(paid, cov.limit)
        remaining = sub(remaining, paid)
        steps.append(Step(cov.name, paid, remaining, cov.id, cov.evidence_ids, None))

    # 4. 给付型：重疾、伤残、身故，独立计算，不抵扣费用
    lump_sums = [lump_sum(cov, inp) for cov in order_lump_sum(active)]

    return ClaimResult(steps=steps, lump_sums=lump_sums, excluded=excluded,
                       out_of_pocket=clamp_zero(remaining))
```

区间运算规则：`sub((a,b),(c,d)) = (max(a-d,0), max(b-c,0))`；`mul((a,b),(r1,r2)) = (a*r1, b*r2)`。每个函数都要有单元测试，至少覆盖：无社保、等待期内出险、两份医疗险叠加、费用低于免赔额、给付型与补偿型同时存在。

### 8.6 续保会话状态机

```python
TRANSITIONS = {
    "START": ["LOAD_BASELINE"],
    "LOAD_BASELINE": ["COLLECT_NEEDS"],
    "COLLECT_NEEDS": ["GAP_CHECK"],
    "GAP_CHECK": ["ASK_USER", "SEARCH"],
    "ASK_USER": ["GAP_CHECK"],
    "SEARCH": ["FETCH_DOCS", "REPORT"],          # 检索失败可直接进入 REPORT 并披露
    "FETCH_DOCS": ["EXTRACT_CANDIDATES", "REPORT"],
    "EXTRACT_CANDIDATES": ["COMPARE"],
    "COMPARE": ["REPORT"],
    "REPORT": ["END"],
}
```

状态由代码推进，模型只能通过工具调用表达意图，代码检查转移是否合法。`GAP_CHECK` 由代码读取 `config/gaps/accident.yaml`，计算未确认维度并按 `weight` 排序，把前两项交给模型改写成自然的问题；模型也可以补充清单外的维度，但必须带 `why` 字段。离开 `GAP_CHECK` 进入 `SEARCH` 的条件：权重 ≥ 0.7 的维度全部确认，或用户明确表示「跳过」。

缺口清单格式：

```yaml
# config/gaps/accident.yaml
category: accident
dimensions:
  - key: travel_mode
    label: 出行方式
    weight: 0.9
    question_hint: 出差主要坐飞机、高铁还是自驾
    options: [飞机为主, 高铁为主, 自驾为主, 混合]
    affects: [transport_extra]
  - key: overseas
    label: 境外出行
    weight: 0.8
    options: [会, 不会, 不确定]
    affects: [accident_medical]
  - key: work_site
    label: 工作场所
    weight: 0.9
    options: [办公室, 工地或厂区, 野外, 混合]
    affects: [occupation_class]
  - key: sudden_death
    label: 猝死责任
    weight: 0.7
    affects: [sudden_death]
  # 其余维度见 PRD 3.10
```

### 8.7 对比矩阵与溯源校验

1. 代码把基线保单与每个候选产品的责任项按 `kind` 对齐，生成行为维度、列为产品的矩阵；单元格值来自已校验的 coverage，缺失显示「条款中未找到」。
2. 模型撰写的差异说明中出现的每个 URL，必须存在于本会话的 `source_record`；每个引用必须通过 8.2 校验。未通过的句子整句移除，并在报告末尾「已移除的未验证内容」中计数。
3. 输出后处理过滤禁用表述：「推荐购买」「最适合」「最划算」「一定能赔」「保证」等，命中时替换为中性表述并记录。

### 8.8 覆盖雷达

每位成员每个维度的有效保额 = 该维度下所有生效且不在等待期的责任项保额之和（医疗类取最高单一限额，不累加）。比例 = 有效保额 / 参考保额，参考保额为 0 或未设置时该维度显示「未设置参考值」，不画点。

### 8.9 PPT 生成与核验

1. `reports/ppt_builder.py` 使用固定模板（16:9），版式、字体、颜色、数字全部由代码写入；模型只返回每页摘要文字，长度上限 90 字。
2. 生成后 `reports/ppt_verify.py` 重新打开文件，读取所有文本框，提取数字，与数据库快照逐一比对，输出 `mismatches` 列表。
3. 若配置了 LibreOffice，转换为 PDF 再用 PyMuPDF 渲染 PNG，交给模型按 `VisualIssues` schema 检查文字溢出、遮挡与重叠；模型发现的问题附带页码与区域描述，代码据此缩小字号或拆页后重新生成，最多两轮。

---

## 9. 测评模式

### 9.1 目标

测评模式服务于 PRD 第 8 章的任务集：同一批输入在多个模型上运行，判定全部由脚本完成，结果可复现、可公开。

### 9.2 命令行

```powershell
cd backend
uv run python -m app.eval run --suite ..\eval\tasks\e3_qa.yaml --model evolving --seed 20260915
uv run python -m app.eval run --suite ..\eval\tasks\e3_qa.yaml --model pro_0628 --seed 20260915
uv run python -m app.eval judge --run-dir ..\eval\runs\<run_id>
uv run python -m app.eval summarize --runs ..\eval\runs --out ..\eval\summary.csv
```

`run` 只负责执行与记录，`judge` 只负责判定，两者分离，判定器修改后可以对历史运行重新判定而不重新调用模型。

### 9.3 任务文件格式

```yaml
# eval/tasks/e3_qa.yaml
suite: e3_qa
version: 1
fixtures_dir: ../../backend/tests/fixtures/policies
tasks:
  - id: e3-01
    documents: [accident_public_a.pdf]
    question: 骑电动车摔伤住院，意外医疗能报吗
    gold:
      verdict: likely_covered
      required_quotes_any:
        - "意外伤害医疗保险金"
  - id: e3-17
    documents: [critical_illness_public_b.pdf]
    question: 近视手术能赔吗
    gold:
      verdict: no_basis
```

私有任务（家庭真实保单）放在 `eval/private/`，格式相同，不进入仓库。

### 9.4 判定器

| 任务 | 判定逻辑 |
|---|---|
| E1/E2 字段抽取 | 字段逐一与 gold 比对；字符串做归一化后完全相等，金额与日期解析后相等；引用通过率来自 verify 结果 |
| E3 问答 | verdict 精确匹配；`required_quotes_any` 至少一条出现在已通过校验的引用中；`no_basis` 题回答为其他结论即判错 |
| E4 理赔事实 | 匹配到的 coverage.kind 集合与 gold 求精确率与召回率；等待期判断逐项比对 |
| E5 缺口追问 | gold 列出必须追问的维度 key，统计会话中 `ask_user` 覆盖的比例，以及到达 SEARCH 前的轮数 |
| E6 检索可信度 | 报告中 URL 是否全部在 `source_record`；注入故障的运行是否在报告中披露；未经校验的产品事实条数 |
| E7 PPT 视觉检查 | 与预置问题清单按页码与问题类型匹配 |

### 9.5 故障注入

```yaml
# eval/tasks/e6_search.yaml 中的片段
faults:
  - tool: search_web
    on_call: 1
    type: timeout          # timeout | empty | http_403 | http_429
  - tool: fetch_document
    on_call: 2
    type: http_403
```

注入由 `eval/faults.py` 包装 SearchProvider 与下载器实现，每次注入写入 `tool_call.injected_fault`。

### 9.6 冻结与披露

1. 正式跑批前，把任务文件、判定器、提示词版本、`uv.lock` 提交并打 tag，例如 `eval-freeze-20260920`。
2. 冻结后发现判定器缺陷，不修改、不重跑，写入 `eval/LIMITATIONS.md`。
3. `summarize` 输出的每一行包含 git commit、提示词版本号、模型 ID、种子。

### 9.7 测评看板

`/eval` 页面读取 `summary.csv` 与 `llm_call` 表：按任务与模型展示成功率、引用通过率、平均 token、平均耗时、重试次数；点击单次运行可查看调用时间线与工具调用序列，便于截图写文章。

---

## 10. 里程碑与分阶段提示词

### 10.1 总计划

| 阶段 | 预计 | 依赖 |
|---|---|---|
| M0 工程骨架与设计系统 | 0.5 天 | 无 |
| M1 成员、上传、渲染、OCR、脱敏 | 1 天 | M0 |
| M2 抽取、校验、核对、保单库与详情 | 1.5 天 | M1 |
| M3 条款问答、理赔模拟 | 1 天 | M2 |
| M4 家庭总览、雷达、提醒 | 0.5 天 | M2 |
| M5 续保顾问（意外险） | 1.5 天 | M2 |
| M6 PPT、测评模式、Docker | 1 天 | M3、M5 |

合计约 7 个工作日。时间不足时按 PRD 优先级砍 P1 功能，M5 可降级为「手动上传候选条款」版本，不做联网检索。

### 10.2 每个阶段的通用提示词前缀

```text
开始前请完整阅读仓库根目录的 AGENTS.md，以及 docs/PRD.md 与 docs/DEV-GUIDE.md 中下面列出的章节。
只实现本阶段范围内的内容，不要提前实现后续阶段的功能，不要修改文档。
遇到文档没有覆盖或互相矛盾的地方，停下来列出问题，不要自行假设后继续。
完成后按 DEV-GUIDE 1.3 的报告纪律提交报告，报告里附测试命令原始输出。
```

### 10.3 M0 工程骨架与设计系统

**阅读章节**：PRD 1、4、5、6；DEV-GUIDE 2、3、4、7。

**提示词**：

```text
[通用前缀]
本阶段目标：搭建前后端工程骨架与设计系统。
1. 按 DEV-GUIDE 第 4 章创建目录结构，后端用 uv 初始化，前端用 Vite + Vue 3 + TypeScript。
2. 后端提供 /api/health 与 /api/settings/models/test（读取 config/models.yaml，对默认模型发起一次最小请求，返回耗时与 token）。
3. 前端实现 tokens.css、glass.css、motion.css，完成应用外壳：环境光背景、响应式导航（桌面侧栏、平板顶栏、手机底栏）、浅色深色主题切换、简洁模式开关，所有页面路由先放占位页。
4. 提供一个 /dev/styleguide 页面，展示色板、字号、按钮、状态徽标、玻璃面板、引用卡片、表单控件。
5. scripts/dev.ps1 同时启动前后端。
```

**验收**：

| 检查项 | 证据 |
|---|---|
| 后端测试通过 | `uv run pytest` 输出 |
| 模型连通 | `/api/settings/models/test` 实际响应体 |
| 前端类型检查与构建 | `pnpm typecheck` 与 `pnpm build` 输出 |
| 设计系统 | styleguide 页在 390 / 820 / 1440 三个宽度、浅色深色两个主题下的 6 张截图 |
| 减少动态效果 | 开启系统设置后环境光静止的截图或录屏说明 |

### 10.4 M1 成员、上传、渲染、OCR、脱敏

**阅读章节**：PRD 3.2、3.3（步骤 1–4）、3.4；DEV-GUIDE 5.1、5.2、5.4、8.1、8.4。

**提示词**：

```text
[通用前缀]
本阶段目标：家庭成员管理，以及上传到脱敏完成为止的处理流程。
1. 建立 member、document、page、pii_mapping、job 表与 Alembic 迁移。
2. 实现持久化任务队列与 SSE 进度推送。
3. 实现 PDF 与图片（含 HEIC）渲染、字符坐标提取、扫描页判定与 RapidOCR 识别。
4. 实现 8.4 的脱敏规则，文本与页图同步打码，映射表加密存储。
5. 前端：成员管理页；上传页（拖拽、多文件、处理进度）；「脱敏前后对比」视图，左右两栏同步滚动。
6. tests/fixtures 中放入合成保单 PDF（由脚本生成，包含虚构的身份证号、手机号、银行卡号、保单号），以及一份扫描风格的图片版本。
不要调用模型。
```

**验收**：脱敏单元测试覆盖 8.4 第 7 条全部情况；合成保单上传后，脱敏页再跑正则命中数为 0 的测试输出；扫描页 OCR 后脱敏同样生效的截图；服务中途重启后任务继续完成的日志。

### 10.5 M2 抽取、校验、核对、保单库与详情

**阅读章节**：PRD 3.3（步骤 5–10）、3.5、3.6、7；DEV-GUIDE 5.3、6、7.8、8.2、8.3。

**提示词**：

```text
[通用前缀]
本阶段目标：模型抽取、引用校验，以及核对、保单库、保单详情三个页面。
1. 实现 LLMProvider 的 ark 与 openai_compat 两个实现，方舟接口参数以官方文档最新示例为准，调用日志写入 llm_call。
2. 实现 classify_pages、extract_policy、extract_coverages 三个提示词与对应 Pydantic 模型。
3. 实现 8.2 引用校验与坐标回算、8.3 金额日期比例解析，状态分为 verified / unverified / not_found / conflict。
4. 前端核对页：左侧字段表单与状态徽标，右侧原文阅读器，点击字段触发 7.8 的引用定位动效。
5. 保单库（卡片与列表视图、筛选、全文检索）与保单详情页。
6. 确认入库后写入 policy、policy_party、coverage、clause、evidence 与 FTS 索引。
```

**验收**：cn_money 与 verify 的单元测试输出；用 3 份公开条款 PDF 跑通抽取的 `llm_call` 记录导出；核对页引用定位动效录屏；手机宽度下阅读器抽屉的截图；伪造一个不存在的 quote 时字段状态为 not_found 的测试输出。

### 10.6 M3 条款问答、理赔模拟

**阅读章节**：PRD 3.7、3.8；DEV-GUIDE 6.3、6.4、8.2、8.5。

**提示词**：

```text
[通用前缀]
本阶段目标：条款问答与理赔情景模拟。
1. 问答：FTS 检索（少于 3 字回退 LIKE）→ 组装条款上下文 → qa_answer 提示词 → 引用校验 → 全部引用失败时降级为 no_basis。SSE 流式输出理由文字，最后推送结构化结果。
2. 理赔：claim_facts 提示词由模型提取事实并匹配责任项；claim/engine.py 按 8.5 实现纯函数计算，禁止在引擎中调用模型或数据库。
3. 前端问答页：范围选择、对话流、引用卡片、原文联动。
4. 前端理赔页：事件表单、ECharts 瀑布图、分保单结果卡、需向保险公司确认事项。
```

**验收**：engine.py 单元测试覆盖 8.5 列出的全部情况，测试输出；问答对一个条款中确无依据的问题返回 no_basis 的接口响应；瀑布图每段点击展开条款依据的截图。

### 10.7 M4 家庭总览、雷达、提醒

**阅读章节**：PRD 3.9、3.11、3.13；DEV-GUIDE 7.7、8.8。

**提示词**：

```text
[通用前缀]
本阶段目标：家庭总览页、覆盖雷达与缺口热力图、到期提醒与 ICS 订阅。
1. /api/overview 返回时间轴区段（等待期、生效、空档）、关键数字与待办。
2. 自研 SVG 时间轴组件，支持缩放与拖动，首次加载绘制动效按 7.7 实现，只执行一次。
3. 成员页展示雷达图，参考保额在设置中维护；热力图点击进入对应保单。
4. APScheduler 每天生成提醒；ICS 订阅地址带随机 token。
```

**验收**：时间轴在三断点的截图；存在断保空档的测试数据下空档正确显示的截图；ICS 文件内容片段。

### 10.8 M5 续保顾问

**阅读章节**：PRD 3.10、8；DEV-GUIDE 6.5、8.6、8.7。

**提示词**：

```text
[通用前缀]
本阶段目标：意外险续保顾问 Agent。
1. 按 8.6 实现状态机，状态由代码推进，模型通过 6.5 列出的工具表达意图。
2. 实现 config/gaps/accident.yaml 与 config/domains.yaml 的加载。
3. search_web 通过 SearchProvider 接口实现，结果按白名单过滤并写入 source_record；fetch_document 实现白名单、SSRF 防护、大小与类型限制，下载后复用 M2 的解析流程。
4. 实现 8.7 对比矩阵、URL 溯源校验与禁用表述过滤。
5. 前端续保页：对话流、追问卡、右侧需求画像卡、对比矩阵、客服问题清单、未取得信息清单。
6. 检索失败时报告中必须出现「检索未完成」及原因。
```

**验收**：fetch_document 拒绝内网地址与非白名单域名的测试输出；模拟 search_web 超时后报告中披露失败的接口响应；一次完整会话从追问到报告的录屏；报告中每个 URL 都能在 source_record 查到的核对脚本输出。

### 10.9 M6 PPT、测评模式、Docker

**阅读章节**：PRD 3.12、3.14、6；DEV-GUIDE 8.9、9、12。

**提示词**：

```text
[通用前缀]
本阶段目标：全家保单 PPT、测评模式、Docker 部署。
1. 按 8.9 实现 PPT 生成、回读核验、可选的视觉检查与自动修正。
2. 按第 9 章实现 eval 命令行、任务文件加载、判定器、故障注入、summary.csv 与 /eval 看板。
3. 按第 12 章编写 Dockerfile 与 compose.yaml，构建 amd64 与 arm64 镜像。
```

**验收**：PPT 回读核验 mismatches 为空的输出；故意改错一个数字后核验报错的测试输出；两个模型在 E3 上各跑一次的 summary.csv；`docker compose up` 后 `/api/health` 的响应；arm64 构建日志末尾。

---

## 11. 测试策略

| 层级 | 工具 | 覆盖重点 |
|---|---|---|
| 单元 | pytest | 脱敏、归一化、引用校验、金额解析、理赔引擎、状态机转移、对比矩阵、禁用表述过滤 |
| 集成 | pytest + respx | 模型 Provider 使用录制的响应回放；解析任务全流程；SSE 事件顺序 |
| 契约 | openapi-typescript | 前端类型由后端 OpenAPI 生成，CI 中检查生成结果与提交一致 |
| 端到端 | Playwright | 上传到确认入库、问答引用定位、理赔模拟、续保会话（模型回放模式） |
| 视觉 | Playwright 截图 | 关键页面在 390 / 820 / 1440、浅色深色下截图，人工比对 |
| 测评 | app.eval | 见第 9 章 |

测试数据原则：仓库中只存放合成保单与保险公司官网公开的条款文件；任何真实家庭保单、截图、模型原始响应都不得提交。模型相关的集成测试默认使用回放，设置 `LIVE_LLM=1` 时才真实调用。

---

## 12. Docker 与 NAS 部署

### 12.1 Dockerfile

```dockerfile
# docker/Dockerfile
FROM node:22-slim AS web
WORKDIR /web
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim AS app
ARG WITH_LIBREOFFICE=false
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 TZ=Asia/Shanghai
RUN apt-get update && apt-get install -y --no-install-recommends \
      libgl1 libglib2.0-0 tzdata \
    && if [ "$WITH_LIBREOFFICE" = "true" ]; then \
         apt-get install -y --no-install-recommends libreoffice-impress-nogui; \
       fi \
    && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev
COPY backend/ ./
COPY config/ /app/config/
COPY frontend/public/fonts/ /usr/share/fonts/policybook/
COPY --from=web /web/dist /app/static
RUN fc-cache -f || true
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["uv", "run", "--no-dev", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

字体复制到系统字体目录，供 PPT 转图片时正确显示中文。LibreOffice 会让镜像增加数百 MB，默认不安装，需要视觉核验时以 `--build-arg WITH_LIBREOFFICE=true` 构建。

### 12.2 compose.yaml

```yaml
# docker/compose.yaml
services:
  policybook:
    image: policybook:latest
    build:
      context: ..
      dockerfile: docker/Dockerfile
    container_name: policybook
    restart: unless-stopped
    env_file: ../.env
    environment:
      DATA_DIR: /data
      MODELS_DIR: /models
    volumes:
      - ./data:/data
      - ./models:/models
    ports:
      - "8080:8000"
```

### 12.3 构建多架构镜像

在 Windows 上使用 Docker Desktop：

```powershell
docker buildx create --use --name pb
docker buildx build --platform linux/amd64,linux/arm64 -f docker/Dockerfile -t <registry>/policybook:0.1.0 --push .
```

没有私有镜像仓库时，可分别构建后 `docker save` 导出为 tar，拷贝到 NAS 上 `docker load`。

### 12.4 NAS 上部署

1. 在 NAS 共享盘创建目录 `policybook/`，放入 `compose.yaml`、`.env`，并建 `data/`、`models/` 子目录；把开发机上已下载的 OCR 模型拷入 `models/`，避免 NAS 首次启动联网下载。
2. 在 NAS 的容器管理界面（群晖 Container Manager、绿联、飞牛、Unraid 等均支持 Compose 项目）以该目录创建项目并启动。
3. 浏览器访问 `http://<NAS内网地址>:8080`，首次进入设置家庭密码与模型 API Key。
4. 不要把端口映射到公网。需要在外面访问时，使用 NAS 自带的 VPN 服务或 WireGuard、Tailscale 这类组网方式。
5. 备份：`data/` 目录纳入 NAS 的快照或定时备份；设置页的「导出全部数据」生成加密 zip，密码单独保管。

### 12.5 升级

```text
1. 设置页导出全部数据
2. 拉取或载入新镜像
3. 重启容器，启动时自动执行 Alembic 迁移
4. 查看 /api/health 与日志确认迁移完成
```

---

## 13. 开发红线清单

以下内容同步写入仓库根目录 `AGENTS.md`，任何一条被违反，该次提交视为不合格。

**数据与隐私**

1. 未经脱敏的页面文本或页图，不得出现在任何模型请求中。
2. 真实保单、真实姓名、证件号、模型原始响应，不得提交到仓库，不得写入日志正文。
3. API Key、APP_SECRET 不得硬编码或提交。

**准确性**

4. 金额、日期、比例、赔付估算的计算只能在代码中完成，模型只返回原文字符串。
5. 未通过引用校验的内容不得以「有依据」的样式展示。
6. 续保报告中的产品事实只能来自已下载并通过校验的文档，URL 必须可在 source_record 中查到。
7. 搜索或下载失败时必须在界面与报告中披露，不得用模型记忆补全。

**合规表述**

8. 不输出购买建议、核保结论、理赔承诺；禁用表述过滤不得绕过。
9. 全站固定免责说明不得删除或折叠隐藏。

**安全**

10. fetch_document 必须校验域名白名单并拒绝内网与保留地址。
11. 所有 API 需要登录，ICS 订阅使用独立随机 token。

**工程**

12. 不得为了通过测试修改断言或删除测试。
13. 汇报必须附命令原始输出，统计数字必须由脚本生成。
14. 不得引入 PRD 与本手册之外的大型依赖（组件库皮肤、CSS 框架、状态管理替代品、外网 CDN 资源），确有需要先提出。
15. 前端不得使用悬停上浮、滚动进场动画、数字滚动计数；带模糊的元素同屏不超过 3 个大面板。
