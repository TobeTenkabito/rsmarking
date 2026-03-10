# RSMarking: High-Performance Remote Sensing Annotation System

遥感影像高性能标注系统

[English](#English Documentation) | [中文](#中文文档)

---



##  English Documentation

### 1. Introduction

**RSMarking** is a microservice-based Remote Sensing (RS) image annotation platform.  
It is designed to handle massive raster datasets (GeoTIFF) and complex vector geometries without the need for heavy pre-processing.

---

### 2. Core Advantages vs Traditional GIS

Compared to traditional GIS servers (e.g., GeoServer, MapServer) or standard web-mapping tools, RSMarking offers:

- **Cython-Accelerated On-the-Fly (OTF) Rendering**

  The built-in **TileEngine** uses C/Cython extensions (`fast_stretch_and_stack`) and `rasterio` window reads to dynamically generate map tiles directly from raw raster files.  
  **Zero pre-tiling required**, saving massive disk space and preprocessing time.

- **Dynamic Multi-Band Stretching**

  Automatically calculates statistics to perform **2%–98% linear stretching** or hardware-accelerated normalization, ensuring optimal visualization for **16-bit/32-bit multi-spectral imagery**.

- **Distributed Microservices Architecture**

  Decoupled **Tile Service** and **Annotation Service** with robust **FastAPI** backends, easily scalable via **Kubernetes**.

---

### 3. Development Setup (Current Dev Stage)

#### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- Node.js 24+

---

#### Step 1: Start Infrastructure & Databases

```bash
cd infrastructure/docker
docker-compose up -d
```

---

#### Step 2: Run Database Migrations

```bash
# Migrate Raster Database
cd infrastructure/db_migrations
alembic upgrade head

# Migrate Vector Annotation Database
cd ../annot_migrations
alembic upgrade head
```

---

#### Step 3: Start Backend Services

```bash
cd services/tile_service
pip install -r requirements.txt
python main.py   # Starts on port 8005
```

---

#### Step 4: Start Frontend

```bash
cd client
npm install
npm run dev
```

---

## 中文文档

### 1. 简介

**RSMarking** 是一个基于 **微服务架构** 的遥感影像标注平台。

系统专为处理 **海量栅格数据集（GeoTIFF）** 和 **复杂矢量几何数据** 而设计，无需繁重的预处理流程即可实现高性能的交互式标注。

---

### 2. 核心特性与优势（对比传统 GIS）

与传统的 GIS 服务器（如 **GeoServer**）或常规 **Web GIS** 平台相比，本项目具有以下显著优势：

- **Cython 加速的即时渲染 (On-the-Fly Rendering)**

  内置的 **TileEngine** 抛弃了传统的“提前切片生成金字塔”方案。  
  通过 `rasterio` 窗口读取结合 **C/Cython 底层扩展 (`fast_stretch_and_stack`)**，直接在内存中动态生成瓦片。  

  **零预处理开销，极大节省磁盘空间与数据准备时间。**

- **动态多波段拉伸算法**

  引擎内置状态管理器，自动计算极值并执行 **16位 / 32位影像** 的线性拉伸或归一化映射。  
  在遇到极值异常时提供高度优化的 **Fallback Process（降级处理策略）**。

- **分布式微服务架构**

  **瓦片服务 (Tile Service)** 与 **标注服务 (Annotation Service)** 完全解耦。  
  通过 **FastAPI** 提供高并发支持，并可通过 **Kubernetes** 实现无缝横向扩展。

---

### 3. 开发环境快速开始（当前开发阶段）

#### 预需求

- Docker & Docker Compose
- Python 3.12+
- Node.js 24+

---

#### 第一步：启动基础设施与数据库

使用 **IaC 配置** 启动数据库实例（PostgreSQL/PostGIS, Redis）。

```bash
cd infrastructure/docker
docker-compose up -d
```

---

#### 第二步：执行数据库迁移脚本

```bash
# 迁移栅格元数据数据库
cd infrastructure/db_migrations
alembic upgrade head

# 迁移矢量标注数据库
cd ../annot_migrations
alembic upgrade head
```

---

#### 第三步：启动后端服务

```bash
cd services/tile_service
pip install -r requirements.txt
python main.py   # 默认在 8005 端口启动
```

---

#### 第四步：启动前端应用

```bash
cd client
npm install
npm run dev
```

---

## 4. Program Construction / 项目结构说明

Please check **start.txt**  
详情查看 **start.txt**

```text
.
├── client                # 前端交互与状态管理 (Vue/React + Leaflet)
├── services              # 后端微服务集群 (FastAPI)
│   ├── tile_service      # 瓦片渲染引擎 (Cython 加速)
│   └── ...
├── infrastructure        # 基础设施即代码 (IaC)
│   ├── docker            # 各模块 Dockerfile 及 Compose
│   ├── kubernetes        # K8s 部署配置文件
│   ├── annot_migrations  # 矢量数据迁移脚本
│   └── db_migrations     # 栅格元数据数据库迁移脚本
└── tests                 # 全局自动化测试 (Pytest & Vitest)
```

---

## 5. 🖼️ Feature Preview / 功能预览

### 5.1 Multi-spectral Image OTF Rendering / 多光谱影像即时渲染

Directly rendering **16-bit GeoTIFF** with dynamic stretching.  
直接渲染 **16位 GeoTIFF** 并应用动态拉伸。

![Figure 5-1 Rendering Example](resources/5_1.png)

---

### 5.2 Interactive Vector Annotation / 交互式矢量标注

Support for complex polygons with **undo/redo** and **topology constraints**.  
支持带 **撤销/重做功能** 及 **拓扑约束** 的复杂多边形标注。

![Figure 5-2 Vector Example](resources/5_2.png)

---

### 5.3 Distributed Service Monitoring / 分布式服务监控

Real-time status of **tile service** and **annotation engine**.  
瓦片服务与标注引擎的实时运行状态。

---

### 5.4 Automated Test Suite / 自动化测试套件

High coverage reports from **Vitest** and **Pytest**.  
来自 **Vitest** 和 **Pytest** 的高覆盖率测试报告。

---

## 6. ⚙️ Performance Results / 性能结果

### 6.1 Rendering Engine Performance / 渲染引擎性能

#### 6.1.1 Concurrency Test / 高并发争抢测试

![Figure 6-1-1 Vector Example](resources/6_1_1.png)

*Relationship between band and latency under high concurrency*

*高并发下波段与延迟的关系*

#### 6.1.2 Rendering Test / 渲染测试

![Figure 6-1-2 Vector Example](resources/6_1_2.png)

*The trend of rendering latency increasing with tile size(3 bands, 128–4096 pixels)*

*渲染延迟随 tile 大小增加的趋势(3 波段，128–4096 像素)*

[Come Back to the Top](#rsmarking-high-performance-remote-sensing-annotation-system)