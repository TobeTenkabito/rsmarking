export const aiModal = `
<div id="ai-modal" class="hidden fixed inset-0 z-[2000] flex items-center justify-center bg-slate-950/55 p-4 backdrop-blur-sm">
    <div id="ai-window"
        class="relative flex flex-col overflow-hidden rounded-2xl bg-white shadow-2xl"
        style="width:min(96vw, 1080px); height:min(90vh, 780px); min-width:min(92vw, 560px); min-height:560px; max-width:calc(100vw - 2rem); max-height:calc(100vh - 2rem); resize:both;">

        <div class="flex items-center justify-between gap-4 border-b border-slate-100 px-6 py-4">
            <div class="flex min-w-0 items-center gap-3">
                <div class="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-slate-900 text-white">
                    <svg class="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v2m0 14v2m9-9h-2M5 12H3m14.95-6.95-1.41 1.41M7.46 16.54l-1.41 1.41m11.9 0-1.41-1.41M7.46 7.46 6.05 6.05M9 12a3 3 0 106 0 3 3 0 00-6 0z"/>
                    </svg>
                </div>
                <div class="min-w-0">
                    <h2 class="truncate text-sm font-black text-slate-800">AI Spatial Assistant</h2>
                    <p id="ai-mode-caption" class="truncate text-[10px] font-bold uppercase tracking-widest text-slate-400">Agent mode</p>
                </div>
            </div>

            <div class="flex shrink-0 items-center gap-2">
                <select id="ai-mode-select" class="hidden" aria-label="Task Mode">
                    <option value="agent" selected>Agent mode</option>
                    <option value="analyze">Analysis Mode</option>
                    <option value="modify">Modify Mode</option>
                </select>
                <div class="grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-1" aria-label="Task Mode">
                    <button id="ai-mode-agent" type="button" data-ai-mode-option="agent" onclick="RS.aiSetMode('agent')"
                        class="ai-mode-option inline-flex h-8 items-center justify-center gap-1.5 rounded-md px-3 text-[11px] font-black transition-all">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h6m-7 8 3-3h8a4 4 0 004-4V8a4 4 0 00-4-4H7a4 4 0 00-4 4v5a4 4 0 004 4"/>
                        </svg>
                        <span>Agent</span>
                    </button>
                    <button id="ai-mode-analyze" type="button" data-ai-mode-option="analyze" onclick="RS.aiSetMode('analyze')"
                        class="ai-mode-option inline-flex h-8 items-center justify-center gap-1.5 rounded-md px-3 text-[11px] font-black transition-all">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 19V5m0 14h16M8 16V9m4 7V7m4 9v-4"/>
                        </svg>
                        <span>Analyze</span>
                    </button>
                    <button id="ai-mode-modify" type="button" data-ai-mode-option="modify" onclick="RS.aiSetMode('modify')"
                        class="ai-mode-option inline-flex h-8 items-center justify-center gap-1.5 rounded-md px-3 text-[11px] font-black transition-all">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m16.5 3.5 4 4L8 20H4v-4L16.5 3.5z"/>
                        </svg>
                        <span>Modify</span>
                    </button>
                </div>
                <button type="button" onclick="RS.closeAIModal()" title="Close"
                    class="flex h-8 w-8 items-center justify-center rounded-lg text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 6l12 12M18 6 6 18"/>
                    </svg>
                </button>
            </div>
        </div>

        <div class="min-h-0 flex-1 space-y-4 overflow-y-auto px-6 py-4 sidebar-scroll">
            <details id="ai-context-panel" class="rounded-lg border border-slate-200 bg-slate-50">
                <summary class="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
                    <div>
                        <div class="text-[11px] font-black uppercase tracking-widest text-slate-500">Context</div>
                        <div id="ai-context-summary" class="mt-0.5 text-[10px] font-medium text-slate-400">Optional in agent mode</div>
                    </div>
                    <svg class="h-4 w-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m6 9 6 6 6-6"/>
                    </svg>
                </summary>
                <div class="grid gap-3 border-t border-slate-200 bg-white p-4 md:grid-cols-3">
                    <div class="space-y-1.5">
                        <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Target Data</label>
                        <select id="ai-target-select"
                            class="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-700 transition-all focus:outline-none focus:ring-2 focus:ring-slate-300">
                        </select>
                    </div>
                    <div class="space-y-1.5">
                        <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Data Type</label>
                        <select id="ai-datatype-select"
                            class="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-700 transition-all focus:outline-none focus:ring-2 focus:ring-slate-300">
                            <option value="raster">Raster Imagery</option>
                            <option value="vector">Vector Layer</option>
                        </select>
                    </div>
                    <div class="space-y-1.5">
                        <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Output Language</label>
                        <select id="ai-language-select"
                            class="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-700 transition-all focus:outline-none focus:ring-2 focus:ring-slate-300">
                            <option value="zh">Chinese</option>
                            <option value="en">English</option>
                            <option value="ja">Japanese</option>
                            <option value="es">Spanish</option>
                        </select>
                    </div>
                </div>
            </details>

            <div id="ai-agent-panel" class="overflow-hidden rounded-lg border border-slate-200 bg-white">
                <div class="flex items-center justify-between border-b border-slate-100 px-4 py-3">
                    <div class="flex min-w-0 items-center gap-2">
                        <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-900 text-[10px] font-black text-white">AI</div>
                        <div class="min-w-0">
                            <div class="truncate text-xs font-black text-slate-700">Agent Chat</div>
                            <div id="ai-agent-session-label" class="font-mono text-[9px] font-bold uppercase tracking-widest text-slate-400"></div>
                        </div>
                    </div>
                    <div class="flex items-center gap-1.5">
                        <button type="button" onclick="RS.aiArchiveConversation()" title="Archive chat"
                            class="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:border-emerald-200 hover:bg-emerald-50 hover:text-emerald-600">
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M7 8v10h10V8M9 12h6M8 4h8l1 4H7l1-4z"/>
                            </svg>
                        </button>
                        <button type="button" onclick="RS.aiToggleArchivePanel()" title="Conversation archive"
                            class="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:border-sky-200 hover:bg-sky-50 hover:text-sky-600">
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 2M4 6h16M5 6v13h14V6M9 3h6"/>
                            </svg>
                        </button>
                        <button type="button" onclick="RS.aiStartNewAgentChat()" title="New chat"
                            class="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-500 transition-all hover:border-slate-300 hover:bg-slate-50 hover:text-slate-700">
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v6h6M20 20v-6h-6M5 19A9 9 0 0119 5M19 5h-5M19 5v5"/>
                            </svg>
                        </button>
                    </div>
                </div>
                <div id="ai-agent-archive-panel" class="hidden border-b border-slate-100 bg-slate-50 px-4 py-3">
                    <div class="mb-2 flex items-center justify-between gap-3">
                        <div class="text-[10px] font-black uppercase tracking-widest text-slate-400">Saved memory</div>
                        <button type="button" onclick="RS.aiClearConversationArchives()"
                            class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[9px] font-black uppercase tracking-widest text-slate-400 hover:border-red-200 hover:bg-red-50 hover:text-red-500">
                            Clear all
                        </button>
                    </div>
                    <div id="ai-agent-archive-list" class="max-h-40 space-y-2 overflow-y-auto sidebar-scroll"></div>
                </div>
                <div id="ai-agent-messages" class="space-y-4 overflow-y-auto bg-slate-50/60 px-4 py-4 sidebar-scroll"
                    style="height:clamp(20rem, 46vh, 36rem); min-height:16rem; max-height:62vh; resize:vertical;"></div>
            </div>

            <div class="space-y-1.5">
                <label id="ai-prompt-label" class="text-[10px] font-black uppercase tracking-widest text-slate-400">Prompt</label>
                <textarea id="ai-prompt-input" rows="2"
                    placeholder="Ask a question or describe a task"
                    class="w-full resize-none rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-700 placeholder-slate-300 transition-all focus:outline-none focus:ring-2 focus:ring-slate-300"></textarea>
                <div id="ai-agent-attachment-controls" class="space-y-2">
                    <input id="ai-agent-file-input" type="file" multiple
                        accept="image/*,.txt,.md,.markdown,.json,.geojson,.csv,.xml,.log,.py,.js,.ts,.html,.css,.yml,.yaml"
                        class="hidden">
                    <div class="flex flex-wrap items-center justify-between gap-2">
                        <button id="ai-agent-attachment-picker" type="button"
                            class="inline-flex h-8 items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 text-[11px] font-black text-slate-600 shadow-sm transition-all hover:border-slate-300 hover:bg-slate-50">
                            <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.5 6.5l-8.9 8.9a3 3 0 104.2 4.2l9.2-9.2a5 5 0 00-7.1-7.1L4.8 12.4"/>
                            </svg>
                            <span>Attach files</span>
                        </button>
                        <div class="text-[10px] font-bold text-slate-400">Images, Markdown, text, JSON, CSV</div>
                    </div>
                    <div id="ai-agent-attachment-list" class="flex flex-wrap gap-2"></div>
                </div>
            </div>

            <details id="ai-function-panel" class="hidden rounded-lg border border-slate-200 bg-white">
                <summary class="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
                    <div class="min-w-0">
                        <div class="text-[11px] font-black uppercase tracking-widest text-slate-500">Advanced functions</div>
                        <div id="ai-function-status" class="mt-0.5 truncate text-[10px] font-bold uppercase tracking-widest text-slate-400">Loading backend functions...</div>
                    </div>
                    <svg class="h-4 w-4 shrink-0 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="m6 9 6 6 6-6"/>
                    </svg>
                </summary>
                <div class="space-y-3 border-t border-slate-100 bg-slate-50 p-4">
                    <div class="flex justify-end">
                        <button type="button" onclick="RS.aiReloadFunctions()"
                            class="rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[10px] font-black text-slate-500 transition-all hover:border-sky-300 hover:text-sky-600">
                            Refresh
                        </button>
                    </div>
                    <div id="ai-function-buttons"></div>
                    <div id="ai-function-detail" class="hidden space-y-3 rounded-lg border border-slate-200 bg-white p-4">
                        <div id="ai-function-summary"></div>
                        <div class="space-y-1.5">
                            <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Arguments JSON</label>
                            <textarea id="ai-function-args-input" rows="7" spellcheck="false"
                                class="w-full resize-y rounded-lg border border-slate-800 bg-slate-950 px-3 py-2.5 font-mono text-[11px] leading-relaxed text-slate-100 transition-all focus:outline-none focus:ring-2 focus:ring-sky-400"></textarea>
                        </div>
                        <div class="grid grid-cols-2 gap-3">
                            <button type="button" onclick="RS.aiResetFunctionArgs()"
                                class="w-full rounded-lg border border-slate-200 bg-slate-50 py-2.5 text-xs font-black text-slate-600 transition-all hover:bg-slate-100 active:scale-[0.98]">
                                Reset Args
                            </button>
                            <button id="ai-function-run-btn" type="button" onclick="RS.aiRunSelectedFunction()"
                                class="w-full rounded-lg bg-sky-600 py-2.5 text-xs font-black text-white shadow-lg shadow-sky-600/15 transition-all hover:bg-sky-700 active:scale-[0.98]">
                                Run Function
                            </button>
                        </div>
                    </div>
                </div>
            </details>

            <div id="ai-error-msg" class="hidden rounded-lg border border-red-100 bg-red-50 px-3 py-2.5 text-xs text-red-600"></div>
            <div id="ai-success-msg" class="hidden rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2.5 text-xs text-emerald-600"></div>

            <div id="ai-result-section" class="hidden space-y-2">
                <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">AI Output</label>
                <pre id="ai-result-content"
                    class="max-h-48 overflow-y-auto whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-700 sidebar-scroll"></pre>
                <a id="ai-download-btn" href="#" download
                    class="hidden flex w-full items-center justify-center gap-2 rounded-lg border border-sky-100 bg-sky-50 px-3 py-2.5 text-xs font-black text-sky-700 transition-all hover:bg-sky-100">
                    <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4-4 4m0 0-4-4m4 4V4"/>
                    </svg>
                    <span>Download Analysis Report</span>
                </a>
            </div>

            <div id="ai-confirm-section" class="hidden grid grid-cols-2 gap-3 pt-1">
                <button onclick="RS.aiConfirmCreate()"
                    class="w-full rounded-lg bg-emerald-600 py-3 text-xs font-black text-white shadow-lg shadow-emerald-600/15 transition-all hover:bg-emerald-700 active:scale-[0.98]">
                    Create Copy
                </button>
                <button onclick="RS.aiConfirmOverwrite()"
                    class="w-full rounded-lg bg-amber-500 py-3 text-xs font-black text-white shadow-lg shadow-amber-500/15 transition-all hover:bg-amber-600 active:scale-[0.98]">
                    Overwrite Original
                </button>
            </div>
        </div>

        <div class="flex items-center justify-between gap-3 border-t border-slate-100 px-6 py-4">
            <button onclick="RS.closeAIModal()"
                class="rounded-lg px-3 py-2 text-[10px] font-black uppercase tracking-widest text-slate-400 transition-colors hover:bg-slate-50 hover:text-slate-600">
                Back to Workspace
            </button>
            <button id="ai-execute-btn" onclick="RS.aiExecute()"
                class="inline-flex min-w-[12rem] items-center justify-center gap-2 rounded-lg bg-slate-900 px-5 py-3 text-sm font-black text-white shadow-xl shadow-slate-900/10 transition-all hover:bg-slate-800 active:scale-[0.98] disabled:cursor-wait disabled:opacity-70">
                <svg id="ai-spinner" class="hidden h-4 w-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                    <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                    <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                </svg>
                <span id="ai-execute-label">Send Message</span>
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
