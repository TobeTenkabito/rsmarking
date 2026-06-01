export const aiModal =`
    <div id="ai-modal" class="hidden fixed inset-0 bg-slate-900/60 backdrop-blur-sm z-[2000] flex items-center justify-center p-4">
    <div id="ai-window" class="bg-white rounded-3xl shadow-2xl relative overflow-hidden flex flex-col"
        style="width:min(96vw, 1080px); height:min(90vh, 780px); min-width:min(92vw, 560px); min-height:560px; max-width:calc(100vw - 2rem); max-height:calc(100vh - 2rem); resize:both;">

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
        <div class="px-8 pb-4 space-y-4 overflow-y-auto sidebar-scroll flex-1 min-h-0">

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
                    <div class="flex items-center space-x-1">
                        <label class="text-[11px] font-bold text-slate-500 uppercase tracking-widest">任务模式</label>
                        <!-- 改进后的提示组件 -->
                        <div class="group relative flex items-center">
                        <svg class="w-3.5 h-3.5 text-slate-400 cursor-help hover:text-violet-500 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"></path>
                        </svg>
                        <div class="invisible group-hover:visible absolute left-0 top-6 w-80 p-0 
                        bg-white text-slate-700 text-[10px] rounded-2xl shadow-xl z-50 
                        opacity-0 group-hover:opacity-100 transition-all duration-300 delay-150 
                        transform -translate-y-1 group-hover:translate-y-0 
                        border border-slate-200">
                        <div class="p-4 overflow-y-auto sidebar-scroll">
                            <div class="font-bold border-b border-slate-200 pb-2 mb-2 text-violet-600">使用说明 / Instructions</div>
                            <div class="space-y-3 leading-relaxed">
                            <p class="text-slate-700">
                                当使用 <span class="text-violet-600 font-semibold">分析模式</span> 时，请尽可能详细地提供数据源（如 "Landsat 7 B1"）和影像类型（如 "DEM" 或 "遥感影像"），以及具体数值代表的物理含义。
                            </p>
                            <p class="text-slate-600">
                                AI 无法得知您从哪里获取的数据，因此提供这些背景信息以便 AI 更好地分析。您对您的数据来源越负责，AI 分析的准确性就越高。
                            </p>
                            <hr class="border-slate-200">
                            <p class="italic text-slate-500">
                                In <span class="text-violet-600 font-semibold">Analysis Mode</span>, please specify the data source (e.g., "Landsat 7 B1"), image type (e.g., "DEM"), and the physical meaning of values. Accurate context leads to higher accuracy.
                            </p>
                            <p class="italic text-slate-400">
                                AI cannot determine the source of your data; therefore, providing this background information enables the AI to perform a more effective analysis. The more diligent you are regarding your data sources, the higher the accuracy of the AI's analysis.
                            </p>
                            </div>
                            </div>
                            <div class="absolute -top-6 left-0 w-full h-6 bg-transparent"></div>
                            <div class="absolute bottom-full left-3 -mb-1 border-4 border-transparent border-b-white"></div>
                            </div>
                            </div>
                    </div>
                    <select id="ai-mode-select"
                        class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 focus:outline-none focus:ring-2 focus:ring-violet-400 transition-all">
                        <option value="analyze">分析模式</option>
                        <option value="modify">修改模式</option>
                        <option value="agent">Agent mode</option>
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
                    placeholder="例：分析该影像的植被覆盖情况\n或：将图层名称修改为更具描述性的名称\nExample: Analyze vegetation coverage in this image\nOr: Rename the layer to something more descriptive"
                    class="w-full text-xs bg-slate-50 border border-slate-200 rounded-xl px-3 py-2.5 text-slate-700 
                    placeholder-slate-300 focus:outline-none focus:ring-2 focus:ring-violet-400 transition-all resize-none"> 
                </textarea> 
            </div>

            <!-- Backend function launcher -->
            <div id="ai-agent-panel" class="hidden overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
                <div class="flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3">
                    <div class="flex items-center gap-2">
                        <div class="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-900 text-[10px] font-black text-white">
                            AI
                        </div>
                        <div>
                            <div class="text-xs font-black text-slate-700">Agent Chat</div>
                            <div id="ai-agent-session-label" class="font-mono text-[9px] font-bold uppercase tracking-widest text-slate-400"></div>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <button type="button" onclick="RS.aiArchiveConversation()"
                            title="Archive chat"
                            class="flex h-8 w-8 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-500 transition-all hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-600">
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M7 8v10h10V8M9 12h6M8 4h8l1 4H7l1-4z"/>
                            </svg>
                        </button>
                        <button type="button" onclick="RS.aiToggleArchivePanel()"
                            title="Conversation archive"
                            class="flex h-8 w-8 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-500 transition-all hover:border-sky-200 hover:bg-sky-50 hover:text-sky-600">
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 2M4 6h16M5 6v13h14V6M9 3h6"/>
                            </svg>
                        </button>
                        <button type="button" onclick="RS.aiStartNewAgentChat()"
                            title="New chat"
                            class="flex h-8 w-8 items-center justify-center rounded-xl border border-slate-200 bg-slate-50 text-slate-500 transition-all hover:border-violet-200 hover:bg-violet-50 hover:text-violet-600">
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v6h6M20 20v-6h-6M5 19A9 9 0 0119 5M19 5h-5M19 5v5"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <div id="ai-agent-archive-panel" class="hidden border-b border-slate-200 bg-white px-4 py-3">
                    <div class="mb-2 flex items-center justify-between gap-3">
                        <div class="text-[10px] font-black uppercase tracking-widest text-slate-400">Saved memory</div>
                        <button type="button" onclick="RS.aiClearConversationArchives()"
                            class="rounded-lg border border-slate-200 px-2 py-1 text-[9px] font-black uppercase tracking-widest text-slate-400 hover:border-red-200 hover:bg-red-50 hover:text-red-500">
                            Clear all
                        </button>
                    </div>
                    <div id="ai-agent-archive-list" class="max-h-40 space-y-2 overflow-y-auto sidebar-scroll"></div>
                </div>
                <div id="ai-agent-messages" class="space-y-4 overflow-y-auto px-4 py-4 sidebar-scroll"
                    style="height:clamp(18rem, 42vh, 34rem); min-height:14rem; max-height:62vh; resize:vertical;"></div>
            </div>

            <div id="ai-function-panel" class="rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-50 to-sky-50/40 p-4 space-y-3">
                <div class="flex items-start justify-between gap-3">
                    <div>
                        <label class="text-[11px] font-black text-slate-600 uppercase tracking-widest">Backend Functions</label>
                        <p class="mt-1 text-[10px] leading-relaxed text-slate-400">
                            Select a registered AI gateway function, edit its JSON arguments, then run it directly.
                        </p>
                    </div>
                    <button type="button" onclick="RS.aiReloadFunctions()"
                        class="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-bold text-slate-500 hover:border-sky-300 hover:text-sky-600 transition-all">
                        Refresh
                    </button>
                </div>

                <div id="ai-function-status"
                    class="text-[10px] font-bold uppercase tracking-widest text-slate-400">
                    Loading backend functions...
                </div>

                <div id="ai-function-buttons" class="grid grid-cols-2 md:grid-cols-3 gap-2"></div>

                <div id="ai-function-detail" class="hidden rounded-2xl border border-slate-200 bg-white p-4 space-y-3">
                    <div id="ai-function-summary"></div>
                    <div class="space-y-1.5">
                        <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Arguments JSON</label>
                        <textarea id="ai-function-args-input" rows="8" spellcheck="false"
                            class="w-full font-mono text-[11px] leading-relaxed bg-slate-950 text-slate-100 border border-slate-800 rounded-2xl px-3 py-2.5 focus:outline-none focus:ring-2 focus:ring-sky-400 transition-all resize-y"></textarea>
                    </div>
                    <div class="grid grid-cols-2 gap-3">
                        <button type="button" onclick="RS.aiResetFunctionArgs()"
                            class="w-full rounded-2xl border border-slate-200 bg-slate-50 py-3 text-xs font-bold text-slate-600 hover:bg-slate-100 transition-all active:scale-[0.98]">
                            Reset Args
                        </button>
                        <button id="ai-function-run-btn" type="button" onclick="RS.aiRunSelectedFunction()"
                            class="w-full rounded-2xl bg-sky-600 py-3 text-xs font-bold text-white shadow-lg shadow-sky-600/20 hover:bg-sky-700 transition-all active:scale-[0.98]">
                            Run Function
                        </button>
                    </div>
                </div>
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
                <a id="ai-download-btn" href="#" download
                    class="hidden w-full flex items-center justify-center space-x-2 text-xs text-violet-600 bg-violet-50 border border-violet-100 rounded-xl px-3 py-2.5 font-bold hover:bg-violet-100 transition-all">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                    </svg>
                    <span>下载分析报告</span>
                </a>
            </div>

            <!-- 修改模式：确认按钮 -->
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

        <!-- 底部操作栏 -->
        <div class="px-8 py-5 border-t border-slate-100 flex flex-col space-y-3">
            <button id="ai-execute-btn" onclick="RS.aiExecute()"
                class="w-full bg-slate-900 hover:bg-slate-800 text-white py-4 rounded-2xl font-bold text-sm shadow-xl transition-all active:scale-[0.98] flex items-center justify-center space-x-2">
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

        <div class="pointer-events-none absolute bottom-2 right-2 text-slate-300">
            <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 20h12M14 14h6M20 8v12"/>
            </svg>
        </div>

    </div>
</div>
    `;
