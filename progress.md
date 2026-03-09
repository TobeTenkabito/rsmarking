# Progress / 进度说明

[中文说明](#中文说明) | [English Version](#english-version)

---

# 中文说明

## 一、修改背景

在原有交互设计中，用户一旦在绘制过程中发生错误，系统往往直接退出整个绘图模式。这种行为会导致操作流程被过度中断，不符合用户的直觉操作习惯。

为了使交互逻辑更加清晰、可控，本次对绘图流程进行了分层设计，将操作状态划分为三个层级：

- **模式（Mode）**
- **功能（Tool / Function）**
- **行动（Action）**

当用户进行取消或撤销操作时，应当明确取消的是哪一个层级，而不是直接强制退出整个绘图模式。

---

## 二、三层交互结构

绘图交互被拆分为三个逻辑层级：

| 层级 | 含义 | 示例 |
|---|---|---|
| **模式（Mode）** | 整体工作环境 | 编辑模式 / 绘图模式 |
| **功能（Tool）** | 当前使用的绘图工具 | 矩形工具 / 多边形工具 |
| **行动（Action）** | 对对象执行的具体操作 | 添加点、删除点、完成绘制 |

可以用一个简单的类比来理解：

- **模式** 相当于进入一间 **画室**
- **功能** 相当于选择 **画笔或刷子**
- **行动** 相当于用工具 **对画布进行具体绘制或修改**

在正常的使用逻辑中，如果只是画错了一条线，用户通常会：

- 使用橡皮擦进行修改  
- 或更换一张画纸重新绘制  

而不是因为一次绘制错误就直接离开整个画室。

---

## 三、修改后的操作逻辑

| 操作场景 | 触发按键 / 动作 | 调用逻辑 | 结果 | 备注 |
|---|---|---|---|---|
| 绘制过程中点选错误 | 右键 / `Backspace` | `deleteLastVertex()` | 删除最后一个顶点，线仍然存在，工具保持激活 | 用于微调 |
| 当前要素绘制失败 | `Esc` | `resetCurrentAction()` | 当前正在绘制的线全部消失，但矩形/多边形工具仍然高亮，可直接重新绘制 | 仅重置行动层 |
| 不想继续绘制当前图层 | 点击工具箱 **取消** | `stopDrawing()` | 工具按钮熄灭，恢复地图平移模式 | 退出功能层 |
| 完全退出编辑模式 | 点击侧边栏 **退出** | `setActiveVectorLayer(null)` | 左侧工具箱隐藏，退出编辑状态 | 退出模式层 |

---

# English Version

## 1. Background

In the previous interaction design, if an error occurred during drawing, the system would often exit the entire drawing mode directly. This behavior interrupts the user's workflow and does not align with natural user expectations.

To improve usability and maintain clearer interaction logic, the drawing workflow has been redesigned into a **three-layer interaction model**.

The operation states are now divided into:

- **Mode**
- **Tool / Function**
- **Action**

When the user performs a cancel or reset operation, the system should clearly determine **which layer should be cancelled**, instead of forcing the user to exit the entire drawing mode.

---

## 2. Three-Layer Interaction Structure

The drawing interaction is divided into three logical layers:

| Layer | Meaning | Example |
|---|---|---|
| **Mode** | Overall working environment | Editing mode / Drawing mode |
| **Tool** | Current drawing tool | Rectangle tool / Polygon tool |
| **Action** | Specific operation on objects | Add vertex, delete vertex, finish drawing |

A simple analogy helps explain the concept:

- **Mode** is like entering an **art studio**
- **Tool** is like choosing a **pen or brush**
- **Action** is the act of **drawing or editing on the canvas**

In real life, if someone draws a line incorrectly, they usually:

- erase part of the drawing, or  
- start again on a new sheet of paper  

They would not leave the entire studio just because of a single mistake.  
The system interaction should follow the same logic.

---

## 3. Updated Interaction Logic

| Scenario | Trigger | Logic | Result | Notes |
|---|---|---|---|---|
| Misplaced vertex during drawing | Right Click / `Backspace` | `deleteLastVertex()` | Only the last vertex is removed, the line remains, tool stays active | Fine adjustment |
| Current feature drawing failed | `Esc` | `resetCurrentAction()` | Current drawing disappears, but rectangle/polygon tool remains active | Reset Action layer |
| User stops drawing on current layer | Click **Cancel** in toolbox | `stopDrawing()` | Tool deactivates and map returns to pan mode | Exit Tool layer |
| Exit editing mode completely | Click **Exit** in sidebar | `setActiveVectorLayer(null)` | Toolbox disappears and editing mode ends | Exit Mode layer |

---

## 4. Interaction Principles

The updated interaction logic follows these principles:

1. **Undo operations should stay at the smallest possible scope (Action layer).**
2. **Tool state should remain stable whenever possible.**
3. **Mode changes should only happen when explicitly triggered by the user.**

This layered structure improves usability and prevents unnecessary interruption of the drawing workflow.