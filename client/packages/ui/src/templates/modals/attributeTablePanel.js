export const attributeTablePanel = `
      <div id="attr-table-panel"
           class="hidden fixed bottom-0 left-0 right-0 bg-white border-t-2 border-slate-200
                  shadow-[0_-6px_24px_rgba(0,0,0,0.08)] z-[2000] flex flex-col
                  transition-all duration-200"
           style="height:280px">

          <!-- 工具栏 -->
          <div id="attr-toolbar"
               class="flex items-center justify-between px-3 py-1.5
                      bg-slate-50 border-b border-slate-200 shrink-0 select-none">

              <!-- 左侧：标题 + 模式徽章 + 状态 -->
              <div class="flex items-center gap-2">
                  <!-- 拖拽纹理 -->
                  <div class="flex flex-col gap-[3px] opacity-25 mr-1 cursor-row-resize"
                       id="attr-drag-handle">
                      <div class="w-5 h-px bg-slate-500"></div>
                      <div class="w-5 h-px bg-slate-500"></div>
                      <div class="w-5 h-px bg-slate-500"></div>
                  </div>

                  <span id="attr-table-title"
                        class="text-xs font-semibold text-slate-600">属性表</span>

                  <!-- 模式徽章：矢量=indigo / 栅格=amber  ← 新增 -->
                  <span id="attr-mode-badge"
                        class="hidden text-[9px] font-bold px-1.5 py-0.5 rounded-full
                               bg-indigo-100 text-indigo-500">
                      矢量
                  </span>

                  <span id="attr-table-loader"
                        class="hidden text-[11px] text-indigo-400 animate-pulse">加载中…</span>
                  <span id="attr-table-count"
                        class="text-[11px] text-slate-400 bg-slate-100
                               px-2 py-0.5 rounded-full"></span>
              </div>

              <!-- 右侧：操作按钮 -->
              <div class="flex items-center gap-1.5">
                  <!-- id="attr-add-col-btn" 供 _syncToolbar() 动态改文案 ← 新增 id -->
                  <button id="attr-add-col-btn"
                          onclick="RS.attrAddColumn()"
                          class="attr-toolbar-btn text-indigo-600 bg-indigo-50
                                 hover:bg-indigo-100 border border-indigo-200">
                      + 新增列
                  </button>
                  <button onclick="RS.attrRefresh()"
                          title="刷新数据"
                          class="attr-toolbar-btn">↻ 刷新</button>
                  <button id="attr-expand-btn"
                          onclick="RS.attrToggleExpand()"
                          title="展开 / 收起"
                          class="attr-toolbar-btn">⬆ 展开</button>
                  <button onclick="RS.attrClose()"
                          title="关闭属性表"
                          class="attr-toolbar-btn hover:text-red-500 hover:bg-red-50">✕</button>
              </div>
          </div>


            <!-- 表格滚动容器 -->
            <div id="attr-scroll" class="flex-1 overflow-auto text-xs">
                <table class="border-collapse w-max min-w-full">
                    <thead id="attr-table-head"></thead>
                    <tbody id="attr-table-body"></tbody>
                </table>
            </div>
        </div>

        <!-- 属性表样式（scoped inline，避免污染全局） -->
        <style>
            .attr-toolbar-btn {
                font-size: 11px;
                padding: 3px 8px;
                border-radius: 5px;
                background: #f1f5f9;
                color: #475569;
                border: 1px solid transparent;
                cursor: pointer;
                transition: background .15s, color .15s;
            }
            .attr-toolbar-btn:hover { background: #e2e8f0; }

            .attr-th {
                position: sticky; top: 0; z-index: 1;
                background: #f1f5f9;
                border: 1px solid #e2e8f0;
                padding: 5px 10px;
                font-size: 11px; font-weight: 600;
                color: #475569;
                white-space: nowrap;
                cursor: pointer;
            }
            .attr-th:hover { background: #e8edf5; }

            .attr-td {
                border: 1px solid #f1f5f9;
                padding: 4px 10px;
                color: #334155;
                white-space: nowrap;
                max-width: 200px;
                overflow: hidden;
                text-overflow: ellipsis;
            }
            .attr-td:hover { background: #f8fafc; }

            .cell-editor {
                width: 100%;
                border: 1.5px solid #6366f1;
                border-radius: 3px;
                padding: 1px 5px;
                font-size: 12px;
                outline: none;
                background: #fff;
            }

            /* 字段类型徽章 */
            .type-badge {
                display: inline-flex;
                align-items: center; justify-content: center;
                width: 15px; height: 15px;
                border-radius: 3px;
                font-size: 9px; font-weight: 700;
                flex-shrink: 0;
            }
            .badge-str  { background:#dbeafe; color:#2563eb; }
            .badge-num  { background:#dcfce7; color:#16a34a; }
            .badge-bool { background:#ffedd5; color:#ea580c; }
            .badge-date { background:#f3e8ff; color:#9333ea; }

            /* 右键菜单 */
            .attr-ctx-menu {
                position: fixed;
                z-index: 9999;
                background: #fff;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                box-shadow: 0 8px 24px rgba(0,0,0,.12);
                padding: 4px 0;
                min-width: 140px;
                font-size: 12px;
            }
            .ctx-item {
                display: block; width: 100%;
                text-align: left;
                padding: 6px 14px;
                transition: background .1s;
                cursor: pointer;
                background: none; border: none;
            }
            .ctx-item:hover    { background: #f1f5f9; }
            .ctx-danger        { color: #ef4444; }
            .ctx-danger:hover  { background: #fef2f2; }
            .ctx-disabled      { color: #cbd5e1; cursor: not-allowed; padding: 6px 14px; display: block; }
            .ctx-sep           { border: none; border-top: 1px solid #f1f5f9; margin: 3px 0; }
        </style>
    `;