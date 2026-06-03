# Progress

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