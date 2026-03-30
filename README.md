# RSMarking · High-Performance Remote Sensing Annotation System
智能遥感影像高性能标注系统

[English](#english) | [中文](#中文)

---

## English

### Introduction

**RSMarking** is a microservice-based remote sensing image annotation platform designed for **massive GeoTIFF datasets** and **complex vector geometries** — with zero heavy pre-processing required.

---

### Core Features

#### ⚡ Cython-Accelerated On-the-Fly Rendering
The built-in **TileEngine** uses C/Cython extensions (`fast_stretch_and_stack`) combined with `rasterio` window reads to generate map tiles dynamically from raw raster files.  
**No pre-tiling, no pyramid generation** — saving disk space and preprocessing time.

#### 🎨 Dynamic Multi-Band Stretching
Automatic **2%–98% linear stretching** and hardware-accelerated normalization for **16-bit / 32-bit multi-spectral imagery**, with an optimized fallback strategy for outlier statistics.

#### 🏗️ Distributed Microservices Architecture
Fully decoupled services (**Tile / Data / Annotation / AI Gateway / Executor**) built on **FastAPI**, horizontally scalable via **Kubernetes**.

#### 🤖 AI Spatial Data Gateway
A dedicated microservice accepting natural language instructions to **analyze or modify** raster/vector GIS data.  
Powered by **LiteLLM** (supports DeepSeek, OpenAI, Azure, etc.) with a strict **Pydantic anti-tamper contract layer** that physically blocks AI from overwriting read-only spatial statistics.

> **vs. QGIS 4.0** — No built-in AI Agent; RSMarking leads in AI-assisted geospatial workflows.  
> **vs. ArcGIS Pro** — ArcGIS Assistant offers deeper analytics, but is commercial; RSMarking is **open and free**.

#### 🗺️ Professional Map Export Module
A fully client-side export pipeline built on the **Canvas 2D API** — no server round-trip required.

| Capability | Detail |
|---|---|
| Formats | PNG (lossless) · JPEG (adjustable quality) · SVG (vector) |
| Resolution | 1x / 2x / 3x / **4x ultra-HD** |
| Layer control | Basemap · Raster · Vector · Decorations (independently toggleable) |
| Graticule | Lat/lon grid lines, **solid or dashed** |
| Frame labels | Cartographic-style coordinate ticks outside map boundary |
| Decorations | Auto scale bar · North arrow · Timestamp watermark |

#### 🐍 Sandboxed Script Executor
Users can submit custom Python 3 scripts that run in **Docker-isolated containers**, with shared `/storage` access and full lifecycle management.

---

### Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                   client (SPA)                      │
│  map.js · modules/ · store/ · UI components         │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / REST
     ┌───────────────┼───────────────────┐
     ▼               ▼                   ▼
tile_service    data_service      annotation_service
(Cython OTF)   (Raster Meta)      (PostGIS Vector)
     │               │                   │
     └───────────────┼───────────────────┘
                     │
            ┌────────┴────────┐
            ▼                 ▼
       ai_gateway      executor_service
      (LiteLLM +       (Docker sandbox)
       Pydantic)
            │
   PostgreSQL/PostGIS + Redis
```

---

### Development Setup

#### Prerequisites
- Docker & Docker Compose
- Python 3.12+
- Node.js 24+

#### Step 1 — Infrastructure

```bash
cd infrastructure/docker
docker-compose up -d
```

#### Step 2 — Database Migrations

```bash
cd infrastructure/db_migrations && alembic upgrade head
cd ../annot_migrations          && alembic upgrade head
```

#### Step 3 — Backend Services

```bash
conda env create -f environment.yml && conda activate <env>

python services/tile_service/main.py
python services/data_service/main.py
python services/annotation_service/main.py
python services/ai_gateway/main.py
python services/executor_service/main.py
```

#### Step 4 — AI Gateway Environment

Create `.env` in the project root:

```env
AI_MODEL=deepseek/deepseek-chat
AI_NAME=deepseek/deepseek-chat
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
```

> Switch to any LiteLLM-compatible provider (OpenAI, Azure, etc.) by changing `AI_MODEL`.

#### Step 5 — Frontend

```bash
cd client && npm install && npm run dev
```

---

### Project Structure

```
.
├── client/                    # Frontend SPA (Vanilla JS + Leaflet)
│   └── packages/
│       ├── app/src/
│       │   ├── modules/       # Feature modules (AI, Export, Annotation, Raster…)
│       │   ├── core/          # UIManager · GlobalBridge · GlobalEvents
│       │   ├── store/         # Central state management
│       │   └── api/           # Service API adapters
│       ├── core/src/map.js    # Map rendering interface
│       └── ui/src/            # Business components & templates
├── services/                  # Backend microservices (FastAPI)
│   ├── tile_service/          # Cython OTF tile engine + LRU cache
│   ├── data_service/          # Raster metadata & band management
│   ├── annotation_service/    # Vector CRUD + PostGIS spatial index
│   ├── ai_gateway/            # LiteLLM adapter + Pydantic anti-tamper
│   └── executor_service/      # Docker-sandboxed script runner
├── functions/                 # Algorithm library
│   └── implement/             # Spectral indices · Extraction · Raster ops
├── infrastructure/            # IaC
│   ├── docker/                # Dockerfiles & Compose
│   ├── kubernetes/            # K8s manifests
│   └── *_migrations/          # Alembic migration scripts
├── storage/
│   ├── cog/                   # Servable COG rasters
│   └── raw/                   # Original imagery
└── tests/                     # Pytest · Vitest · Playwright (planned)
```

---

### Feature Preview

#### Multi-spectral OTF Rendering
Direct rendering of 16-bit GeoTIFF with dynamic band stretching.

![Rendering Example](resources/5_1.png)

#### Interactive Vector Annotation
Complex polygon annotation with undo/redo and topology constraints.

![Vector Annotation](resources/5_2.png)

#### AI Gateway — Analyze Mode
Submit a natural language query to receive a professional spatial analysis report.

![AI Analyze](resources/5_4_1.png)

#### AI Gateway — Modify Mode
Issue a natural language instruction; AI returns a Pydantic-validated JSON diff for confirmation before committing to DB.

![AI Modify](resources/5_4_2.png)

#### Map Export Module
Export the live map view as a high-resolution image with cartographic decorations.

![Export Preview](resources/8_1.png)

---

### Performance Highlights

#### Concurrency Test
![Concurrency](resources/6_1_1.png)
*Band count vs. latency under high concurrency*

#### Rendering Benchmark
![Rendering](resources/6_1_2.png)
*Rendering latency vs. tile size (3 bands, 128–4096 px)*

---

### AI Gateway — Architecture Deep Dive

#### Request Flow

```
POST /ai/process  { target_id, data_type, mode, language, user_prompt, overwrite }
    │
    ▼
router.py → translator.py
    ├─ 1. Extract Context  (RasterContextData | VectorContextData)
    ├─ 2. Build Prompt     (ANALYZE: free-form | MODIFY: strict JSON Schema)
    ├─ 3. Call LLM         (LiteLLM acompletion + auto-retry)
    └─ 4. Validate & Write
           ├── ANALYZE → plain text report
           └── MODIFY  → schema_validator.py (Pydantic anti-tamper)
                             ├── overwrite=true  → UPDATE DB
                             └── overwrite=false → CREATE new record
```

#### API — `POST /ai/process`

| Field | Type | Required | Description |
|---|---|---|---|
| `target_id` | `int \| str` | ✅ | Raster `index_id` or Vector Layer UUID |
| `data_type` | `raster \| vector` | ✅ | Data type |
| `mode` | `analyze \| modify` | ✅ | Task mode |
| `language` | `zh \| en \| ja` | — | Response language (default: `zh`) |
| `user_prompt` | `string` | ✅ | Natural language instruction (2–2000 chars) |
| `overwrite` | `bool` | — | Overwrite original record (default: `false`) |

![AI Gateway Architecture](resources/7_1.png)

---

## 中文

### 简介

**RSMarking** 是一个基于**微服务架构**的遥感影像标注平台，专为处理**海量 GeoTIFF 栅格数据**与**复杂矢量几何**而设计，无需繁重预处理即可实现高性能交互式标注。

---

### 核心特性

#### ⚡ Cython 加速即时渲染 (OTF)
内置 **TileEngine** 通过 `rasterio` 窗口读取结合 **C/Cython 扩展 (`fast_stretch_and_stack`)**，直接在内存中动态生成瓦片。  
**零预切片、零金字塔构建**，极大节省磁盘空间与数据准备时间。

#### 🎨 动态多波段拉伸
自动执行 **16位 / 32位影像**的 **2%–98% 线性拉伸**或归一化映射，并在统计异常时触发优化降级策略。

#### 🏗️ 分布式微服务架构
**瓦片 / 数据 / 标注 / AI 网关 / 脚本执行**服务完全解耦，基于 **FastAPI** 提供高并发支持，可通过 **Kubernetes** 横向扩展。

#### 🤖 AI 空间数据智能网关
独立微服务，接受自然语言指令对栅格/矢量 GIS 数据执行**智能分析**或**结构化修改**。  
通过 **LiteLLM** 统一适配多种大模型，并以严格的 **Pydantic 契约层**物理拦截 AI 对只读空间统计字段的篡改。

> **对比 QGIS 4.0** — 尚无内置 AI Agent；RSMarking 在 AI 辅助遥感工作流上具备先发优势。  
> **对比 ArcGIS Pro** — ArcGIS Assistant 分析深度更强，但属商业付费软件；RSMarking **开源免费**。

#### 🗺️ 专业地图视图导出模块
基于 **Canvas 2D API** 的全客户端导出管线，无需任何服务端请求。

| 能力 | 说明 |
|---|---|
| 导出格式 | PNG（无损）· JPEG（可调质量）· SVG（矢量） |
| 分辨率 | 1x / 2x / 3x / **4x 超高清** |
| 图层控制 | 底图 · 栅格 · 矢量 · 装饰元素（独立开关） |
| 经纬网格 | 全图覆盖，支持**实线 / 虚线** |
| 外框标注 | 专业制图风格的经纬度刻度，与网格独立控制 |
| 内置装饰 | 自动比例尺 · 指北针 · 时间戳水印 |

#### 🐍 沙箱脚本执行器
用户可提交自定义 Python 3 脚本，在 **Docker 容器隔离**环境中运行，支持共享 `/storage` 访问与完整生命周期管理。

---

### 架构概览

```
┌─────────────────────────────────────────────────────┐
│                前端单页应用 (SPA)                    │
│  map.js · modules/ · store/ · UI 组件               │
└────────────────────┬────────────────────────────────┘
                     │ HTTP / REST
     ┌───────────────┼───────────────────┐
     ▼               ▼                   ▼
tile_service    data_service      annotation_service
(Cython OTF)  (栅格元数据管理)    (PostGIS 矢量标注)
     │               │                   │
     └───────────────┼───────────────────┘
                     │
            ┌────────┴────────┐
            ▼                 ▼
       ai_gateway      executor_service
      (LiteLLM +       (Docker 沙箱)
       Pydantic)
            │
   PostgreSQL/PostGIS + Redis
```

---

### 开发环境快速开始

#### 预需求
- Docker & Docker Compose
- Python 3.12+
- Node.js 24+

#### 第一步 — 启动基础设施

```bash
cd infrastructure/docker
docker-compose up -d
```

#### 第二步 — 数据库迁移

```bash
cd infrastructure/db_migrations && alembic upgrade head
cd ../annot_migrations          && alembic upgrade head
```

#### 第三步 — 启动后端服务

```bash
conda env create -f environment.yml && conda activate <env>

python services/tile_service/main.py
python services/data_service/main.py
python services/annotation_service/main.py
python services/ai_gateway/main.py
python services/executor_service/main.py
```

#### 第四步 — 配置 AI 网关环境变量

在项目根目录创建 `.env`：

```env
AI_MODEL=deepseek/deepseek-chat
AI_NAME=deepseek/deepseek-chat
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
```

> 仅需修改 `AI_MODEL` 即可切换至 DeepSeek、OpenAI、Azure OpenAI 等任意 LiteLLM 兼容提供商。

#### 第五步 — 启动前端

```bash
cd client && npm install && npm run dev
```

---

### 项目结构

```
.
├── client/                    # 前端单页应用 (Vanilla JS + Leaflet)
│   └── packages/
│       ├── app/src/
│       │   ├── modules/       # 功能模块 (AI · 导出 · 标注 · 栅格…)
│       │   ├── core/          # UIManager · GlobalBridge · GlobalEvents
│       │   ├── store/         # 核心状态管理
│       │   └── api/           # 各服务 API 适配层
│       ├── core/src/map.js    # 地图渲染核心接口
│       └── ui/src/            # 业务组件与 HTML 模板
├── services/                  # 后端微服务 (FastAPI)
│   ├── tile_service/          # Cython OTF 渲染引擎 + LRU 缓存
│   ├── data_service/          # 栅格元数据与波段管理
│   ├── annotation_service/    # 矢量 CRUD + PostGIS 空间索引
│   ├── ai_gateway/            # LiteLLM 适配 + Pydantic 防篡改
│   └── executor_service/      # Docker 沙箱脚本执行器
├── functions/                 # 算法函数库
│   └── implement/             # 光谱指数 · 目标提取 · 栅格运算
├── infrastructure/            # 基础设施即代码 (IaC)
│   ├── docker/                # Dockerfile & Compose
│   ├── kubernetes/            # K8s 部署配置
│   └── *_migrations/          # Alembic 迁移脚本
├── storage/
│   ├── cog/                   # 可服务 COG 栅格
│   └── raw/                   # 原始影像
└── tests/                     # Pytest · Vitest · Playwright（规划中）
```

---

### 功能预览

#### 多光谱影像即时渲染
直接渲染 16 位 GeoTIFF，动态波段拉伸。

![渲染示例](resources/5_1.png)

#### 交互式矢量标注
支持撤销/重做与拓扑约束的复杂多边形标注。

![矢量标注](resources/5_2.png)

#### AI 网关 — 分析模式
提交自然语言问题，获取专业空间数据分析报告。

![AI 分析](resources/5_4_1.png)

#### AI 网关 — 修改模式
自然语言指令驱动元数据修改，AI 返回经 Pydantic 校验的 JSON 差异供确认后落库。

![AI 修改](resources/5_4_2.png)

#### 地图视图导出
将当前地图视图导出为高分辨率图像，支持专业制图装饰元素。

![导出预览](resources/8_1.png)

---

### 性能结果

#### 高并发争抢测试
![并发测试](resources/6_1_1.png)
*高并发下波段数与延迟的关系*

#### 渲染性能测试
![渲染测试](resources/6_1_2.png)
*渲染延迟随 Tile 尺寸增加的趋势（3 波段，128–4096 像素）*

---

### AI 网关架构详解

#### 请求流程

```
POST /ai/process  { target_id, data_type, mode, language, user_prompt, overwrite }
    │
    ▼
router.py → translator.py
    ├─ 1. 提取上下文  (RasterContextData | VectorContextData)
    ├─ 2. 构建 Prompt (ANALYZE: 自由报告 | MODIFY: 严格 JSON Schema)
    ├─ 3. 调用 LLM   (LiteLLM acompletion + 自动重试)
    └─ 4. 校验与写入
           ├── ANALYZE → 返回纯文本报告
           └── MODIFY  → schema_validator.py (Pydantic 防篡改)
                             ├── overwrite=true  → UPDATE DB
                             └── overwrite=false → CREATE 新记录
```

#### 接口说明 — `POST /ai/process`

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `target_id` | `int \| str` | ✅ | 栅格 `index_id` 或矢量图层 UUID |
| `data_type` | `raster \| vector` | ✅ | 数据类型 |
| `mode` | `analyze \| modify` | ✅ | 任务模式 |
| `language` | `zh \| en \| ja` | — | 响应语言（默认 `zh`） |
| `user_prompt` | `string` | ✅ | 自然语言指令（2–2000 字符） |
| `overwrite` | `bool` | — | 是否覆盖原记录（默认 `false`，创建新记录） |

![AI 网关架构图](resources/7_1.png)