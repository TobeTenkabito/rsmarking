export const attributeTablePanel = `
      <div id="attr-table-panel"
           class="hidden fixed bg-white border border-slate-200 rounded-md
                  shadow-[0_12px_36px_rgba(15,23,42,0.16)] z-[2000] flex flex-col
                  transition-shadow duration-150 attr-floating-panel"
           style="width:min(920px, calc(100vw - 24px)); height:280px; left:12px; top:calc(100vh - 292px);">

          <div class="attr-resize-handle attr-resize-n"  data-attr-resize="n"></div>
          <div class="attr-resize-handle attr-resize-e"  data-attr-resize="e"></div>
          <div class="attr-resize-handle attr-resize-s"  data-attr-resize="s"></div>
          <div class="attr-resize-handle attr-resize-w"  data-attr-resize="w"></div>
          <div class="attr-resize-handle attr-resize-ne" data-attr-resize="ne"></div>
          <div class="attr-resize-handle attr-resize-nw" data-attr-resize="nw"></div>
          <div class="attr-resize-handle attr-resize-se" data-attr-resize="se"></div>
          <div class="attr-resize-handle attr-resize-sw" data-attr-resize="sw"></div>

          <!-- Toolbar -->
          <div id="attr-toolbar"
               class="flex items-center justify-between px-3 py-1.5
                      bg-slate-50 border-b border-slate-200 shrink-0 select-none cursor-move rounded-t-md">

              <!-- Left side：Title + Mode badge + English -->
              <div class="flex items-center gap-2">
                  <!-- Drag texture -->
                  <div class="flex flex-col gap-[3px] opacity-25 mr-1 cursor-move"
                       id="attr-drag-handle">
                      <div class="w-5 h-px bg-slate-500"></div>
                      <div class="w-5 h-px bg-slate-500"></div>
                      <div class="w-5 h-px bg-slate-500"></div>
                  </div>

                  <span id="attr-table-title"
                        class="text-xs font-semibold text-slate-600">Attribute table</span>

                  <!-- Mode badge：Vector=indigo / English=amber  ← English -->
                  <span id="attr-mode-badge"
                        class="hidden text-[9px] font-bold px-1.5 py-0.5 rounded-full
                               bg-indigo-100 text-indigo-500">
                      Vector
                  </span>

                  <span id="attr-table-loader"
                        class="hidden text-[11px] text-indigo-400 animate-pulse">Loading…</span>
                  <span id="attr-table-count"
                        class="text-[11px] text-slate-400 bg-slate-100
                               px-2 py-0.5 rounded-full"></span>
              </div>

              <!-- Right side：ActionsEnglish -->
              <div class="flex items-center gap-1.5">
                  <!-- id="attr-add-col-btn" English _syncToolbar() English ← English id -->
                  <button id="attr-add-col-btn"
                          onclick="RS.attrAddColumn()"
                          class="attr-toolbar-btn text-indigo-600 bg-indigo-50
                                 hover:bg-indigo-100 border border-indigo-200">
                      + Add Column
                  </button>
                  <button onclick="RS.attrExportCsv()"
                          title="Export CSV"
                          class="attr-toolbar-btn">CSV</button>
                  <button onclick="RS.attrRefresh()"
                          title="Refresh data"
                          class="attr-toolbar-btn">↻ Refresh</button>
                  <button id="attr-expand-btn"
                          onclick="RS.attrToggleExpand()"
                          title="Expand / Collapse"
                          class="attr-toolbar-btn">⬆ Expand</button>
                  <button onclick="RS.attrClose()"
                          title="Close attribute table"
                          class="attr-toolbar-btn hover:text-red-500 hover:bg-red-50">✕</button>
              </div>
          </div>


            <!-- Table scroll container -->
            <div id="attr-scroll" class="flex-1 overflow-auto text-xs">
                <table class="border-collapse w-max min-w-full">
                    <thead id="attr-table-head"></thead>
                    <tbody id="attr-table-body"></tbody>
                </table>
            </div>
        </div>

        <!-- Attribute table styles（scoped inline，avoid global style leakage） -->
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

            .attr-floating-panel {
                min-width: 360px;
                min-height: 180px;
                max-width: calc(100vw - 12px);
                max-height: calc(100vh - 12px);
                box-sizing: border-box;
            }
            .attr-floating-panel.is-moving {
                box-shadow: 0 18px 42px rgba(15,23,42,0.22);
            }
            .attr-resize-handle {
                position: absolute;
                z-index: 3;
                background: transparent;
            }
            .attr-resize-n,
            .attr-resize-s {
                left: 10px;
                right: 10px;
                height: 8px;
                cursor: ns-resize;
            }
            .attr-resize-n { top: -4px; }
            .attr-resize-s { bottom: -4px; }
            .attr-resize-e,
            .attr-resize-w {
                top: 10px;
                bottom: 10px;
                width: 8px;
                cursor: ew-resize;
            }
            .attr-resize-e { right: -4px; }
            .attr-resize-w { left: -4px; }
            .attr-resize-ne,
            .attr-resize-nw,
            .attr-resize-se,
            .attr-resize-sw {
                width: 14px;
                height: 14px;
            }
            .attr-resize-ne { top: -5px; right: -5px; cursor: nesw-resize; }
            .attr-resize-nw { top: -5px; left: -5px; cursor: nwse-resize; }
            .attr-resize-se { bottom: -5px; right: -5px; cursor: nwse-resize; }
            .attr-resize-sw { bottom: -5px; left: -5px; cursor: nesw-resize; }

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

            /* field type badge */
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

            /* context menu */
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
