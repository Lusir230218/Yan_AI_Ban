# 研AI伴

> AI 驱动的考研学习操作系统 —— 多智能体协作 · 知识图谱 · GraphRAG · 飞轮自校准

[![Stage](https://img.shields.io/badge/Stage-5-blueviolet)](#项目阶段)
[![Backend](https://img.shields.io/badge/Backend-FastAPI%200.136-009688.svg)](backend/)
[![Frontend](https://img.shields.io/badge/Frontend-Vue%203.5%20%2B%20TS%206.0-42b883.svg)](frontend/)
[![KG](https://img.shields.io/badge/KG-Neo4j%20CE-008cc1.svg)](#数据层)
[![Python](https://img.shields.io/badge/Python-3.12-3776ab.svg)](#环境要求)

---

## 目录

- [项目简介](#项目简介)
- [核心亮点](#核心亮点)
- [系统架构](#系统架构)
- [项目阶段](#项目阶段)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [运行与调试](#运行与调试)
- [环境变量](#环境变量)
- [测试](#测试)
- [API 总览](#api-总览)
- [文档索引](#文档索引)
- [常见问题](#常见问题)

---

## 项目简介

**研AI伴** 不是一个传统题库,而是一个 **AI 驱动的考研学习操作系统**。它把"学—练—评—调—励"五个环节交给一组协同的多智能体,并以一张覆盖数学、英语、政治的知识图谱作为底层事实库,用 GraphRAG 抑制 LLM 的幻觉、用周级飞轮不断校准图谱置信度。

| 维度     | 传统考研产品       | 研AI伴                              |
| -------- | ------------------ | ----------------------------------- |
| 学习路径 | 千人一面           | 多智能体协作,千人千面              |
| 反馈机制 | 对错判断           | 错因深层分析 + 知识图谱定位         |
| 评估方式 | 模考分数           | 日常数据驱动的分数预测 + 风险预警   |
| 心理维度 | 无                 | 疲劳检测 + 情感识别 + 主动干预      |
| 内容形式 | 文字为主           | 多模态(拍照/语音/手写/PDF)          |

代码与文档遵循"**阶段(Stage)× 子项目(2A/2B/2C/2D)**"的演进式组织方式,每一阶段都有独立的设计文档、评测脚本和验收标准。

---

## 核心亮点

- 🧠 **多智能体编排**:Planner / Tutor / Evaluator / Encourager 四个 Agent,通过 LangGraph `Supervisor` 进行单意图路由与多意图并行分发([`backend/agents/supervisor.py`](backend/agents/supervisor.py))。
- 🕸️ **知识图谱基座**:7 种概念类型、8 类关系,统一的本体约束与 Neo4j schema 生成器([`backend/kg/ontology.py`](backend/kg/ontology.py), [`backend/kg/schema.py`](backend/kg/schema.py))。
- 🛠️ **LLM 抽取 Pipeline**:从教科书 docx 自动抽取概念/关系,带去重、合并、跨学科置信度衰减([`backend/kg/extract.py`](backend/kg/extract.py))。
- 🔎 **GraphRAG 检索**:向量召回 + 图遍历 + LLM 生成,显著降低幻觉([`backend/kg/graph_rag.py`](backend/kg/graph_rag.py))。
- 🔁 **飞轮自校准**:周级 EMA 校准概念 confidence、检测冲突关系、导出 admin review queue([`backend/kg/flywheel.py`](backend/kg/flywheel.py))。
- 📷 **多模态 AI 解答**:OCR + GPT-4o Vision + Tutor 多轮对话([`backend/api/v1/ai_solve.py`](backend/api/v1/ai_solve.py))。
- 📈 **学习分析与预测**:用户知识点掌握度快照、分数预测、错题变式出题([`docs/阶段四-分数预测.md`](docs/阶段四-分数预测.md), [`docs/阶段三-错题管理与变式出题.md`](docs/阶段三-错题管理与变式出题.md))。
- 📊 **Prometheus 指标**:`/metrics` 端点挂载,飞轮运行/信号/争议等核心指标可观测([`backend/main.py:55`](backend/main.py#L55))。

---

## 系统架构

```
┌────────────────────────── 前端层 (Vue 3 + TS + Vite + Element Plus) ──────────────────────────┐
│  Web SPA (管理员后台 / 学习面板 / 知识图谱可视化)                                              │
└──────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                       │ HTTPS / WebSocket
┌──────────────────────────────────────▼───────────────────────────────────────────────────────┐
│                          FastAPI 主服务 (backend/main.py)                                     │
│  ┌────────────┬────────────┬────────────┬────────────┬────────────┬────────────┐              │
│  │ /api/v1/   │ /api/v1/   │ /api/v1/   │ /api/v1/   │ /api/v1/   │ /api/v1/   │              │
│  │ auth       │ study      │ questions  │ ai-solve   │ kg         │ kg/admin   │              │
│  │ users      │ evaluation │ supervisor │ encourager │ analytics  │ feedback   │              │
│  └────────────┴────────────┴────────────┴────────────┴────────────┴────────────┘              │
│                                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                  多智能体编排层 (LangGraph Supervisor)                                    │  │
│  │   intent_router → call_tutor | call_evaluator | call_encourager | call_planner           │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                                │
│  ┌──────────────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         AI 服务层                                                         │  │
│  │   LLM Gateway (OpenAI 兼容 + Anthropic 兼容 STAGE5)                                       │  │
│  │   Embedding Service   ·   OCR/Vision   ·   阶段五·2B 知识抽取   ·   阶段五·2C GraphRAG     │  │
│  └──────────────────────────────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────┬───────────────────────────────────────────────────────┘
                                       │
┌──────────────────────────────────────▼───────────────────────────────────────────────────────┐
│                                          数据层                                                 │
│   PostgreSQL (SQLAlchemy async)  ·  Neo4j CE (知识图谱)  ·  APScheduler (飞轮)                │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

> 完整方案图参见 [`docs/项目方案.md`](docs/项目方案.md);阶段演进图位于 [`figures/`](figures/) 目录。

---

## 项目阶段

仓库按"**阶段 × 子任务**"组织。每个阶段都有独立的设计文档、评测脚本与可演示产物。

| 阶段       | 主题             | 文档                                                                    |
| ---------- | ---------------- | ----------------------------------------------------------------------- |
| 阶段一     | 多智能体编排     | [`docs/阶段一-多智能体编排.md`](docs/阶段一-多智能体编排.md)             |
| 阶段二     | Question 与时间维度、算法说明、实施详解、知识图谱与 GraphRAG | [`docs/阶段二-*.md`](docs/)             |
| 阶段三     | 错题管理与变式出题 | [`docs/阶段三-错题管理与变式出题.md`](docs/阶段三-错题管理与变式出题.md) |
| 阶段四     | 分数预测         | [`docs/阶段四-分数预测.md`](docs/阶段四-分数预测.md)                     |
| 阶段五·2A  | 知识图谱基座     | [`docs/阶段五-2A-知识图谱基座.md`](docs/阶段五-2A-知识图谱基座.md)     |
| 阶段五·2B  | LLM 抽取 pipeline | [`docs/阶段五-2B-LLM抽取pipeline.md`](docs/阶段五-2B-LLM抽取pipeline.md) |
| 阶段五·2C  | GraphRAG 检索集成 | [`docs/阶段五-2C-GraphRAG检索集成.md`](docs/阶段五-2C-GraphRAG检索集成.md) |
| 阶段五·2D  | 飞轮机制         | [`docs/阶段五-2D-飞轮机制.md`](docs/阶段五-2D-飞轮机制.md)               |

---

## 技术栈

### 后端

| 类别       | 选型                                                                 |
| ---------- | -------------------------------------------------------------------- |
| Web 框架   | FastAPI 0.136 · Uvicorn · Starlette                                  |
| 数据       | SQLAlchemy 2.0 (async) · asyncpg · PostgreSQL                        |
| 知识图谱   | neo4j 6.x · Neo4j CE                                                 |
| AI 编排    | LangGraph · LangChain Core · Anthropic SDK(阶段五·2B STAGE5 LLM)    |
| 多模态     | OpenAI Vision (GPT-4o) · PaddleOCR · Docling                         |
| 调度       | APScheduler (飞轮周级批跑 + 知识点快照)                             |
| 可观测性   | prometheus_client                                                    |
| 安全       | python-jose · passlib · bcrypt                                       |
| 测试       | pytest · pytest-asyncio                                              |

### 前端

| 类别   | 选型                                                                       |
| ------ | -------------------------------------------------------------------------- |
| 框架   | Vue 3.5 + TypeScript 6.0 + Vite 8.0                                        |
| UI     | Element Plus · @element-plus/icons-vue · @kjgl77/datav-vue3               |
| 状态   | Pinia 3.0                                                                  |
| 路由   | vue-router 4.6                                                             |
| 数学   | KaTeX                                                                      |
| 可视化 | three.js (3D 知识图谱)                                                     |
| HTTP   | axios 1.17                                                                 |

---

## 目录结构

```
project/
├── backend/                  # FastAPI 后端
│   ├── main.py               # 应用入口 (lifespan: 启动 Neo4j schema / 飞轮 / 快照)
│   ├── config.py             # Pydantic Settings 配置
│   ├── api/v1/               # 路由(认证/用户/学习/题库/AI解答/评估/鼓励/对话/分析/KG/飞轮/反馈)
│   ├── agents/               # LangGraph 多智能体 (supervisor / planner / tutor / evaluator / encourager / ai_solve)
│   ├── kg/                   # 阶段五·2A~2D 知识图谱子系统(ontology/extract/rag/flywheel)
│   ├── llm/gateway.py        # LLM 网关(OpenAI 兼容 + STAGE5 Anthropic 兼容)
│   ├── core/                 # 数据库、安全
│   ├── models/               # SQLAlchemy ORM
│   ├── schemas/              # Pydantic 模型
│   ├── services/             # 业务服务(掌握度计算、用户状态)
│   ├── jobs/                 # 异步任务(每日快照)
│   ├── data/                 # 教科书样本 / 抽取中间产物
│   └── tests/                # pytest
│
├── frontend/                 # Vue 3 + TS 前端
│   ├── src/                  # 业务代码
│   ├── package.json          # Vite + Vue 3.5
│   └── vite.config.ts
│
├── docs/                     # 阶段设计文档与方案
├── figures/                  # 阶段流程图 / 架构图
├── requirements.txt          # 后端依赖(UTF-16 编码)
├── neo4j-ce.zip              # Neo4j CE 安装包(可选)
└── README.md                 # 你正在看的这个文件
```

---

## 环境要求

| 依赖        | 版本                  | 备注                                  |
| ----------- | --------------------- | ------------------------------------- |
| Python      | 3.12+                 | `backend/.venv` 已配                  |
| Node.js     | ≥ 20.19 或 ≥ 22.12    | 见 `frontend/package.json` 的 `engines` |
| PostgreSQL  | 14+                   | 业务库(用户/学习/题/反馈)             |
| Neo4j       | 5.x CE                | 知识图谱(可选:仅阶段五需要)          |
| Redis       | 可选                  | 预留缓存位                            |

> 没有 Neo4j 也能跑阶段一~四;阶段五需要 Neo4j。`KG_ENV=production` 时**不会**自动写 schema,避免污染生产库。

---

## 快速开始

### 1. 克隆 & 初始化

```bash
git clone <your-repo-url> project
cd project
```

### 2. 启动后端

```bash
cd backend

# 创建虚拟环境(可选,.venv 已存在)
# python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux / macOS
# source .venv/bin/activate

# 安装依赖(requirements.txt 是 UTF-16 编码,Windows 下 pip 直接支持;若失败先用 iconv 转 UTF-8)
pip install -r ../requirements.txt

# 复制环境变量模板并填写
cp .env.example .env       # Linux/macOS
# copy .env.example .env    # Windows

# 运行开发服务器
uvicorn main:app --reload
```

启动后可访问:

- Swagger UI:<http://localhost:8000/docs>
- ReDoc:<http://localhost:8000/redoc>
- 健康检查:<http://localhost:8000/>
- Prometheus 指标:<http://localhost:8000/metrics>

### 3. 启动前端

```bash
cd frontend
npm install
npm run dev
```

默认地址:<http://localhost:5173>。已配置 CORS 允许该来源。

### 4.(可选)启动 Neo4j

使用 [`neo4j-ce.zip`](neo4j-ce.zip) 或 `neo4j-desktop.exe` 启动本地实例,把账号密码写入 `backend/.env` 的 `NEO4J_*` 与 `STAGE5_LLM_*`。然后:

```bash
# 仅 dev/staging 会自动 apply schema;production 不会
KG_ENV=dev uvicorn main:app --reload
```

---

## 运行与调试

| 任务                   | 命令                                                                  |
| ---------------------- | --------------------------------------------------------------------- |
| 后端开发模式(HMR)      | `uvicorn main:app --reload`                                           |
| 类型/契约检查(后端)    | `pytest backend/tests -q`                                             |
| 前端类型检查 + 构建    | `cd frontend && npm run build`                                        |
| 前端 dev server        | `cd frontend && npm run dev`                                          |
| 手动触发飞轮批跑       | `POST /api/v1/kg/admin/flywheel/run-flywheel`(需 admin)               |
| 知识抽取一次           | `python -m kg.extract --help`                                          |
| 启动 LangSmith 追踪    | 设置 `LANGSMITH_*` 环境变量后启动(已依赖 `langsmith`)                |

---

## 环境变量

完整字段见 [`backend/config.py`](backend/config.py) 与 [`backend/.env.example`](backend/.env.example)。最小可运行配置:

```ini
# 业务数据库
DATABASE_URL=postgresql+asyncpg://postgres:your-password@localhost:5432/jianyan
SECRET_KEY=change-me-in-production-use-openssl-rand-hex-32

# Neo4j(知识图谱)
NEO4J_HOST=127.0.0.1
NEO4J_PORT=7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your-neo4j-password

# 主 LLM(OpenAI 兼容)
LLM_API_KEY=sk-your-key-here
LLM_BASE_URL=https://api.openai-proxy.org/v1
LLM_MODEL=qwen3.5-flash
LLM_VISION_MODEL=gpt-4o

# 阶段五·2B 独立 LLM(Anthropic 兼容协议:STAGE5)
STAGE5_LLM_API_KEY=sk-your-key-here
STAGE5_LLM_BASE_URL=https://api.minimaxi.com/anthropic
STAGE5_LLM_MODEL=MiniMax-M3

# 知识图谱环境:dev 启动时会 apply schema;production 不会
KG_ENV=dev
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
INITIAL_CONFIDENCE=0.5

# 定时任务
MASTERY_RECOMPUTE_ON_ANSWER=true
SNAPSHOT_CRON_HOUR=2
```

> ⚠️ 真实密钥请写入 `backend/.env`(已加入 `.gitignore`),不要提交到仓库。

---

## 测试

```bash
cd backend
pytest -q
```

测试覆盖阶段五各子系统的关键路径(本体校验、抽取、图谱检索、飞轮 EMA、争议检测等)。pytest 配置见 [`backend/pytest.ini`](backend/pytest.ini)。

---

## API 总览

所有接口挂载在 `/api/v1` 下,详见 [`backend/api/v1/router.py`](backend/api/v1/router.py)。

| 模块                  | 路径前缀                          | 说明                                                |
| --------------------- | --------------------------------- | --------------------------------------------------- |
| 认证 / 用户           | `/api/v1/auth`、`/api/v1/users`   | JWT 登录、用户信息                                  |
| 学习 / 题库           | `/api/v1/study`、`/api/v1/questions` | 学习计划、题目检索                                |
| AI 解答               | `/api/v1/ai-solve`                | 单次 OCR / Vision 解答、Tutor 多轮对话             |
| 多智能体对话          | `/api/v1/supervisor`              | 意图路由 + 多 Agent 并发                            |
| 评估 / 鼓励           | `/api/v1/evaluation`、`/api/v1/encourager` | 分数评估、心理鼓励                       |
| 学习分析              | `/api/v1/analytics`               | 掌握度、错因分布                                    |
| 知识图谱检索          | `/api/v1/kg`                      | GraphRAG、概念详情、相似概念、推荐                  |
| KG Admin(2B)          | `/api/v1/kg/admin`                | 抽取候选 review-queue                               |
| 飞轮 Admin(2D)        | `/api/v1/kg/admin/flywheel`       | 争议 review、合并、归档、批跑触发、概览指标         |
| 用户反馈              | `/api/v1/feedback`                | 答案对错反馈、缺口问题                              |

---

## 文档索引

仓库内 [`docs/`](docs/) 目录收录了各阶段的详细设计与实施记录(推荐按顺序阅读):

- [`docs/项目方案.md`](docs/项目方案.md) — 总体技术方案
- [`docs/项目计划书.md`](docs/项目计划书.md) — 项目计划
- [`docs/数学大纲.md`](docs/数学大纲.md) — 数学子学科大纲
- [`docs/题库重构方案.md`](docs/题库重构方案.md) — 题库模型
- [`docs/实现方案.md`](docs/实现方案.md) / [`docs/AI解答方案.md`](docs/AI解答方案.md) — AI 解答多模态方案
- [`docs/AI辅导功能实现.md`](docs/AI辅导功能实现.md) / [`docs/多智能体实现说明.md`](docs/多智能体实现说明.md) — 智能体实现
- [`docs/阶段一-多智能体编排.md`](docs/阶段一-多智能体编排.md) ~ [`docs/阶段五-2D-飞轮机制.md`](docs/阶段五-2D-飞轮机制.md) — 各阶段设计文档

配套架构图位于 [`figures/`](figures/):

- `figures/stage3-wrong-answer-loop/`
- `figures/stage5-2b-extract-pipeline/`
- `figures/stage5-2c-graph-rag-pipeline/`
- `figures/stage5-2d-flywheel-pipeline/`

---

## 常见问题

<details>
<summary><b>Neo4j db 名要用 <code>kg-dev</code> 吗?</b></summary>

是。带连字符的 db 名在 Cypher 里需要用反引号包裹。`kg-dev` / `kg-staging` / `kg-prod` 三套环境已与 `KG_ENV` 一一对应(`kg-dev` ⇄ `dev`,依此类推)。`CREATE DATABASE` 必须 `WAIT` 才能继续。

</details>

<details>
<summary><b>为什么我改了图谱 schema 但 Neo4j 没生效?</b></summary>

`KG_ENV=production` 时 `init_kg_schema` 会被短路,不会触碰现有库。请把 `KG_ENV=dev` 才能在启动时自动 apply。生产环境请走迁移流程。

</details>

<details>
<summary><b>requirements.txt 装不上?</b></summary>

该文件为 **UTF-16 LE** 编码(Windows 习惯)。新版 pip 已支持,如果你的客户端过旧可先转码:

```bash
iconv -f UTF-16LE -t UTF-8 requirements.txt > requirements.utf8.txt
pip install -r requirements.utf8.txt
```

</details>

<details>
<summary><b>pytest 报 <i>event loop closed</i> / driver 残留?</b></summary>

`kg.neo4j_client` 使用模块级 `_driver` 单例,每个异步测试**末尾必须** `await kg.neo4j_client.close_kg_driver()`,否则下一个测试会拿到已关闭的连接。详见 [`backend/tests/`](backend/tests/) 中的 fixture 模式。

</details>

<details>
<summary><b>阶段五·2B 的 LLM 为什么跟主 LLM 配置分开?</b></summary>

知识抽取需要长上下文 + 结构化输出,选用 Anthropic 兼容协议(`STAGE5_LLM_*`)与主对话 LLM 解耦,便于独立调优。Embedding 仍复用主 OpenAI 兼容配置。

</details>

---

## License

MIT © LovMay AI Project