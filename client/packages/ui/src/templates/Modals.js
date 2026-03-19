/**
 * Modals.js - 存放所有大型 HTML 骨架片段
 * 这种方式可以将 HTML 与主逻辑解耦，保持 index.html 的整洁
 */
export const ModalTemplates = {
    // 1. 指数计算弹窗骨架 (NDVI, NDWI 等)
    indexModal: `
        <div id="index-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
            <div class="bg-white w-full max-w-sm rounded-3xl p-8 shadow-2xl relative overflow-hidden">
                <div id="index-modal-bar" class="absolute top-0 left-0 w-full h-1.5 bg-indigo-500"></div>
                <div id="index-content"></div>
                <div class="pt-6 flex flex-col space-y-3">
                    <button onclick="RS.executeIndexCalculation()" class="w-full bg-slate-900 hover:bg-slate-800 text-white py-4 rounded-2xl font-bold text-sm shadow-xl transition-all active:scale-[0.98]">执行空间运算</button>
                    <button onclick="RS.closeIndexModal()" class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">返回工作站</button>
                </div>
            </div>
        </div>
    `,

    // 2. 要素提取弹窗骨架 (植被、水体提取等)
    extractionModal: `
        <div id="extraction-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
            <div class="bg-white w-full max-w-sm rounded-3xl p-8 shadow-2xl relative overflow-hidden">
                <div id="extraction-modal-bar" class="absolute top-0 left-0 w-full h-1.5 bg-indigo-500"></div>
                <div id="extraction-content"></div>
                <div class="pt-6 flex flex-col space-y-3">
                    <button onclick="RS.runExtraction()" class="w-full bg-slate-900 hover:bg-slate-800 text-white py-4 rounded-2xl font-bold text-sm shadow-xl transition-all active:scale-[0.98]">开始自动化提取</button>
                    <button onclick="RS.closeExtractionModal()" class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">取消任务</button>
                </div>
            </div>
        </div>
    `,

    // 3. 波段合成弹窗骨架
    mergeModal: `
        <div id="merge-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
            <div class="bg-white w-full max-w-md rounded-2xl shadow-2xl overflow-hidden">
                <div class="p-5 border-b border-slate-100 flex justify-between items-center bg-slate-50/50">
                    <h3 class="font-bold text-slate-800 uppercase text-xs tracking-widest">波段合成 (Band Stacking)</h3>
                    <button onclick="RS.closeMergeModal()" class="text-slate-400 hover:text-slate-600 transition-colors">✕</button>
                </div>
                <div id="merge-selection-list" class="p-5 max-h-[400px] overflow-y-auto space-y-2 bg-white"></div>
                <div class="p-5 bg-slate-50 border-t border-slate-100 flex justify-end items-center space-x-4">
                    <button onclick="RS.closeMergeModal()" class="px-4 py-2 text-xs font-bold text-slate-400">取消</button>
                    <button id="confirm-merge-btn" onclick="RS.executeMerge()" disabled class="bg-indigo-600 text-white px-6 py-2 rounded-lg text-xs font-bold shadow-lg disabled:opacity-50">确认合成</button>
                </div>
            </div>
        </div>
    `,

    // 栅格计算器骨架
calculatorModal: `
    <div id="calculator-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
        <div class="bg-white w-full max-w-lg rounded-3xl p-8 shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
            <div class="absolute top-0 left-0 w-full h-1.5 bg-purple-500"></div>
            
            <div class="flex justify-between items-center mb-6">
                <h2 class="text-xl font-black text-slate-800 tracking-tight">栅格计算器</h2>
                <button onclick="RS.toggleCalcHelp()" class="flex items-center space-x-1 text-slate-400 hover:text-purple-600 transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                    <span class="text-[10px] font-bold uppercase">语法帮助</span>
                </button>
            </div>

            <div id="calc-help-panel" class="hidden mb-4 p-4 bg-purple-50 rounded-2xl border border-purple-100 text-[11px] text-purple-800 leading-relaxed animate-in fade-in slide-in-from-top-2">
                <p class="font-bold mb-1">💡 语法说明：</p>
                <ul class="list-disc list-inside space-y-1 opacity-80">
                    <li>使用 <code class="bg-purple-200 px-1 rounded">A, B, C...</code> 代表下方绑定的影像图层</li>
                    <li>条件运算：<code class="bg-purple-200 px-1 rounded">where(条件, 真值, 假值)</code></li>
                    <li>示例：<code class="bg-purple-200 px-1 rounded">where(A > 0.5, A * 1.2, 0)</code></li>
                    <li>支持：<code class="bg-purple-200 px-1 rounded">sin, cos, log, exp, sqrt, abs</code></li>
                </ul>
            </div>
            
            <div class="space-y-4 overflow-y-auto pr-2 custom-scrollbar">
                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">数学表达式</label>
                    <input type="text" id="calc-expression-input" placeholder="例如: (A + B) / sqrt(C)" 
                           onkeyup="RS.updateCalculatorVariables()"
                           class="w-full p-4 bg-slate-50 border border-slate-200 rounded-xl text-sm font-mono outline-none focus:ring-2 focus:ring-purple-500/20">
                    
                    <div class="flex flex-wrap gap-1.5 mt-2">
                        ${['sin', 'cos', 'log', 'sqrt', 'exp', 'abs', 'where'].map(fn => `
                            <button onclick="RS.insertCalcFunction('${fn}')" class="px-2.5 py-1 bg-slate-100 hover:bg-purple-100 hover:text-purple-700 text-slate-500 rounded-md text-[10px] font-mono font-bold transition-all border border-slate-200/50">
                                ${fn}()
                            </button>
                        `).join('')}
                        <button onclick="RS.insertCalcFunction('where')" class="px-2.5 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-600 rounded-md text-[10px] font-mono font-bold transition-all border border-indigo-100">
                            where(c,x,y)
                        </button>
                    </div>
                </div>

                <div id="calc-variables-container" class="space-y-2"></div>

                <div>
                    <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">结果图层名称</label>
                    <input type="text" id="calc-name-input" value="Calc_Result" class="w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm outline-none">
                </div>
            </div>

            <div class="pt-6 flex flex-col space-y-3">
                <button onclick="RS.executeCalculator()" class="w-full bg-purple-600 hover:bg-purple-700 text-white py-4 rounded-2xl font-bold text-sm shadow-xl">执行运算</button>
                <button onclick="RS.closeCalculatorModal()" class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">取消</button>
            </div>
        </div>
    </div>
`,
    // 脚本编辑器弹窗骨架
    scriptModal: `
        <div id="script-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
            <div class="bg-white w-full max-w-4xl h-[85vh] rounded-3xl shadow-2xl relative overflow-hidden flex flex-col">
                <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-purple-500 to-pink-500"></div>
                
                <!-- 头部 -->
                <div class="p-6 border-b border-slate-100 flex justify-between items-center">
                    <div class="flex items-center space-x-3">
                        <div class="p-2 bg-purple-100 rounded-lg">
                            <svg class="w-5 h-5 text-purple-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4"></path>
                            </svg>
                        </div>
                        <div>
                            <h2 class="text-lg font-black text-slate-800">Python 脚本编辑器</h2>
                            <p class="text-xs text-slate-500">在安全沙箱环境中执行自定义遥感算法</p>
                        </div>
                    </div>
                    <button onclick="RS.closeScriptEditor()" class="text-slate-400 hover:text-slate-600 transition-colors p-2">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                
                <!-- 内容区域 -->
                <div id="script-content" class="flex-1 overflow-auto">
                    <!-- 动态内容 -->
                </div>
                
                <!-- 底部操作栏 -->
                <div class="p-6 border-t border-slate-100 bg-slate-50/50 flex justify-between items-center">
                    <div class="flex items-center space-x-4">
                        <button onclick="RS.clearScriptEditor()" class="text-xs text-slate-500 hover:text-slate-700">
                            清空编辑器
                        </button>
                        <button onclick="RS.showScriptHistory()" class="text-xs text-slate-500 hover:text-slate-700">
                            历史记录
                        </button>
                    </div>
                    <div class="flex items-center space-x-3">
                        <button id="script-cancel-btn" onclick="RS.closeScriptEditor()" class="px-6 py-2.5 text-sm font-bold text-slate-500 hover:text-slate-700 transition-colors">
                            取消
                        </button>
                        <button id="script-execute-btn" onclick="RS.executeScript()" class="px-8 py-2.5 bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 text-white rounded-xl font-bold text-sm shadow-xl transition-all active:scale-[0.98] disabled:opacity-50 disabled:cursor-not-allowed">
                            执行脚本
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `,

    // 右下角详情面板
    detailPanel: `
        <div id="detail-panel" class="hidden fixed right-6 bottom-10 w-80 bg-white/95 backdrop-blur-md shadow-2xl rounded-2xl p-5 z-[1002] border border-slate-100 custom-shadow">
            <div class="flex justify-between items-start mb-4">
                <h3 class="font-bold text-slate-800 text-xs truncate max-w-[180px]" id="detail-title">影像详情</h3>
                <button onclick="RS.hideDetail()" class="text-slate-400 hover:text-slate-600">✕</button>
            </div>
            <div id="detail-content" class="text-slate-600 overflow-y-auto max-h-[300px]"></div>
        </div>
    `,
        // AI 智能助手弹窗骨架
    aiModal: `
        <div id="ai-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
            <div class="bg-white w-full max-w-lg rounded-3xl shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">

                <!-- 顶部色条 -->
                <div class="absolute top-0 left-0 w-full h-1.5 bg-gradient-to-r from-violet-500 to-indigo-500"></div>

                <!-- 头部 -->
                <div class="p-8 pb-4">
                    <div class="flex items-center space-x-3 mb-1">
                        <div class="p-2 bg-violet-50 rounded-xl">
                            <svg class="w-5 h-5 text-violet-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.347.347A3.75 3.75 0 0112 18.75a3.75 3.75 0 01-2.651-1.098l-.347-.347z"/>
                            </svg>
                        </div>
                        <div>
                            <h2 class="text-base font-bold text-slate-800">AI 空间智能助手</h2>
                            <p class="text-[10px] text-slate-400 font-medium">分析数据 · 智能修改元数据</p>
                        </div>
                    </div>
                </div>

                <!-- 表单区（可滚动） -->
                <div class="px-8 pb-4 space-y-4 overflow-y-auto sidebar-scroll flex-1">

                    <!-- 目标数据 + 数据类型 -->
                    <div class="grid grid-cols-2 gap-3">
                        <div class="space-y-1.5">
                            <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">目标数据</label>
                            <select id="ai-target-select"
                                class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-400 transition-all">
                            </select>
                        </div>
                        <div class="space-y-1.5">
                            <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">数据类型</label>
                            <select id="ai-datatype-select"
                                class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-400 transition-all">
                                <option value="raster">栅格影像</option>
                                <option value="vector">矢量图层</option>
                            </select>
                        </div>
                    </div>

                    <!-- 任务模式 + 语言 -->
                    <div class="grid grid-cols-2 gap-3">
                        <div class="space-y-1.5">
                            <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">任务模式</label>
                            <select id="ai-mode-select"
                                class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-400 transition-all">
                                <option value="analyze">分析模式</option>
                                <option value="modify">修改模式</option>
                            </select>
                        </div>
                        <div class="space-y-1.5">
                            <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">输出语言</label>
                            <select id="ai-language-select"
                                class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-400 transition-all">
                                <option value="zh">中文</option>
                                <option value="en">English</option>
                                <option value="ja">日本語</option>
                            </select>
                        </div>
                    </div>

                    <!-- 指令输入框 -->
                    <div class="space-y-1.5">
                        <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">指令</label>
                        <textarea id="ai-prompt-input" rows="3"
                            placeholder="例：分析该影像的植被覆盖情况，或：将图层名称修改为更具描述性的名称"
                            class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-violet-400 transition-all resize-none">
                        </textarea>
                    </div>

                    <!-- 错误 / 成功提示 -->
                    <div id="ai-error-msg"
                        class="hidden text-xs text-red-600 bg-red-50 border border-red-100 rounded-xl px-3 py-2.5">
                    </div>
                    <div id="ai-success-msg"
                        class="hidden text-xs text-emerald-600 bg-emerald-50 border border-emerald-100 rounded-xl px-3 py-2.5">
                    </div>

                    <!-- 结果展示区 -->
                    <div id="ai-result-section" class="hidden space-y-2">
                        <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">AI 输出</label>
                        <pre id="ai-result-content"
                            class="text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 whitespace-pre-wrap break-words max-h-48 overflow-y-auto sidebar-scroll">
                        </pre>
                        <!-- 分析模式下载按钮 -->
                        <a id="ai-download-btn" href="#" download
                            class="hidden w-full flex items-center justify-center space-x-2 text-xs text-violet-600 bg-violet-50 border border-violet-100 rounded-xl px-3 py-2.5 font-bold hover:bg-violet-100 transition-all">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                            </svg>
                            <span>下载分析报告</span>
                        </a>
                    </div>

                    <!-- 修改模式：新建 / 覆盖 确认按钮 -->
                    <div id="ai-confirm-section" class="hidden grid grid-cols-2 gap-3 pt-1">
                        <button onclick="RS.aiConfirmCreate()"
                            class="w-full bg-emerald-500 hover:bg-emerald-600 text-white py-3 rounded-2xl font-bold text-xs shadow-lg shadow-emerald-500/20 transition-all active:scale-[0.98]">
                            ✦ 新建副本
                        </button>
                        <button onclick="RS.aiConfirmOverwrite()"
                            class="w-full bg-amber-500 hover:bg-amber-600 text-white py-3 rounded-2xl font-bold text-xs shadow-lg shadow-amber-500/20 transition-all active:scale-[0.98]">
                            ⚠ 覆盖原始
                        </button>
                    </div>

                </div>

                <!-- 底部操作栏（固定） -->
                <div class="px-8 py-5 border-t border-slate-100 flex flex-col space-y-3">
                    <button id="ai-execute-btn" onclick="RS.aiExecute()"
                        class="w-full bg-slate-900 hover:bg-slate-800 text-white py-4 rounded-2xl font-bold text-sm shadow-xl transition-all active:scale-[0.98] flex items-center justify-center space-x-2">
                        <!-- 加载动画 -->
                        <svg id="ai-spinner" class="hidden animate-spin w-4 h-4 text-white" fill="none" viewBox="0 0 24 24">
                            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                        </svg>
                        <span>执行 AI 任务</span>
                    </button>
                    <button onclick="RS.closeAIModal()"
                        class="w-full text-slate-400 text-[10px] font-bold uppercase tracking-widest py-2">
                        返回工作站
                    </button>
                </div>

            </div>
        </div>
    `,
        // --- 8. 属性表底部抽屉骨架 ---
    attributeTablePanel: `
        <div id="attr-table-panel"
             class="hidden fixed bottom-0 left-0 right-0 bg-white border-t-2 border-slate-200
                    shadow-[0_-6px_24px_rgba(0,0,0,0.08)] z-[2000] flex flex-col
                    transition-all duration-200"
             style="height:280px">

            <!-- 工具栏 -->
            <div id="attr-toolbar"
                 class="flex items-center justify-between px-3 py-1.5
                        bg-slate-50 border-b border-slate-200 shrink-0 select-none">

                <!-- 左侧：标题 + 状态 -->
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
                    <span id="attr-table-loader"
                          class="hidden text-[11px] text-indigo-400 animate-pulse">加载中…</span>
                    <span id="attr-table-count"
                          class="text-[11px] text-slate-400 bg-slate-100
                                 px-2 py-0.5 rounded-full"></span>
                </div>

                <!-- 右侧：操作按钮 -->
                <div class="flex items-center gap-1.5">
                    <button onclick="RS.attrAddColumn()"
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
    `,
};