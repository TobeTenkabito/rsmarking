export const aiModal = `
<div id="ai-modal" class="hidden fixed inset-0 z-[2000] flex items-center justify-center bg-slate-950/50 p-4 backdrop-blur-sm">
    <div id="ai-window"
        class="relative flex flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl"
        style="width:min(96vw, 1080px); height:min(90vh, 780px); min-width:min(92vw, 560px); min-height:560px; max-width:calc(100vw - 2rem); max-height:calc(100vh - 2rem); resize:both;">

        <div class="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-100 px-4">
            <div class="flex min-w-0 items-center gap-2">
                <div class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-900 text-[10px] font-black text-white">AI</div>
                <div class="min-w-0">
                    <h2 class="truncate text-sm font-black text-slate-800">AI Spatial Assistant</h2>
                    <p id="ai-mode-caption" class="truncate text-[9px] font-black uppercase tracking-widest text-slate-400">Agent mode</p>
                </div>
            </div>

            <div class="flex shrink-0 items-center gap-1.5">
                <select id="ai-mode-select" aria-label="Task Mode"
                    class="h-8 rounded-md border border-slate-200 bg-white px-2.5 text-[11px] font-black text-slate-600 outline-none transition-colors hover:border-slate-300 focus:ring-2 focus:ring-slate-200">
                    <option value="agent" selected>Agent mode</option>
                    <option value="analyze">Analysis Mode</option>
                    <option value="modify">Modify Mode</option>
                </select>

                <details id="ai-context-panel" class="relative">
                    <summary title="Context" class="flex h-8 w-8 cursor-pointer list-none items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 7h16M7 12h10M10 17h4"/>
                        </svg>
                    </summary>
                    <div class="absolute right-0 top-10 z-50 rounded-lg border border-slate-200 bg-white p-4 shadow-2xl"
                        style="width:min(88vw,40rem);">
                        <div class="mb-3 flex items-center justify-between gap-3">
                            <div>
                                <div class="text-[10px] font-black uppercase tracking-widest text-slate-500">Context</div>
                                <div id="ai-context-summary" class="mt-0.5 text-[10px] font-medium text-slate-400">Optional in agent mode</div>
                            </div>
                        </div>
                        <div class="grid gap-3 md:grid-cols-3">
                            <div class="space-y-1.5">
                                <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Target Data</label>
                                <select id="ai-target-select"
                                    class="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 transition-all focus:outline-none focus:ring-2 focus:ring-slate-300">
                                </select>
                            </div>
                            <div class="space-y-1.5">
                                <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Data Type</label>
                                <select id="ai-datatype-select"
                                    class="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 transition-all focus:outline-none focus:ring-2 focus:ring-slate-300">
                                    <option value="raster">Raster Imagery</option>
                                    <option value="vector">Vector Layer</option>
                                </select>
                            </div>
                            <div class="space-y-1.5">
                                <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Output Language</label>
                                <select id="ai-language-select"
                                    class="w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 transition-all focus:outline-none focus:ring-2 focus:ring-slate-300">
                                    <option value="zh">Chinese</option>
                                    <option value="en">English</option>
                                    <option value="ja">Japanese</option>
                                    <option value="es">Spanish</option>
                                </select>
                            </div>
                        </div>
                    </div>
                </details>

                <details id="ai-function-panel" class="hidden relative">
                    <summary title="Tools" class="flex h-8 w-8 cursor-pointer list-none items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6h10M4 6h2m4 6h10M4 12h2m4 6h10M4 18h2"/>
                        </svg>
                    </summary>
                    <div class="absolute right-0 top-10 z-50 rounded-lg border border-slate-200 bg-white p-4 shadow-2xl"
                        style="width:min(88vw,56rem);">
                        <div class="mb-3 flex items-center justify-between gap-3">
                            <div class="min-w-0">
                                <div class="text-[10px] font-black uppercase tracking-widest text-slate-500">Tools</div>
                                <div id="ai-function-status" class="mt-0.5 truncate text-[10px] font-bold uppercase tracking-widest text-slate-400">Loading backend functions...</div>
                            </div>
                            <button type="button" onclick="RS.aiReloadFunctions()"
                                class="rounded-md border border-slate-200 bg-white px-2.5 py-1.5 text-[10px] font-black text-slate-500 transition-all hover:border-sky-300 hover:text-sky-600">
                                Refresh
                            </button>
                        </div>
                        <div id="ai-function-buttons"></div>
                        <div id="ai-function-detail" class="mt-3 hidden space-y-3 rounded-md border border-slate-200 bg-white p-3">
                            <div id="ai-function-summary"></div>
                            <div class="space-y-1.5">
                                <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">Arguments JSON</label>
                                <textarea id="ai-function-args-input" rows="6" spellcheck="false"
                                    class="w-full resize-y rounded-md border border-slate-800 bg-slate-950 px-3 py-2.5 font-mono text-[11px] leading-relaxed text-slate-100 transition-all focus:outline-none focus:ring-2 focus:ring-sky-400"></textarea>
                            </div>
                            <div class="grid grid-cols-2 gap-3">
                                <button type="button" onclick="RS.aiResetFunctionArgs()"
                                    class="w-full rounded-md border border-slate-200 bg-slate-50 py-2.5 text-xs font-black text-slate-600 transition-all hover:bg-slate-100 active:scale-[0.98]">
                                    Reset Args
                                </button>
                                <button id="ai-function-run-btn" type="button" onclick="RS.aiRunSelectedFunction()"
                                    class="w-full rounded-md bg-sky-600 py-2.5 text-xs font-black text-white shadow-lg shadow-sky-600/15 transition-all hover:bg-sky-700 active:scale-[0.98]">
                                    Run Function
                                </button>
                            </div>
                        </div>
                    </div>
                </details>

                <details class="relative">
                    <summary title="Conversation actions" class="flex h-8 w-8 cursor-pointer list-none items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 12h.01M12 12h.01M18 12h.01"/>
                        </svg>
                    </summary>
                    <div class="absolute right-0 top-10 z-50 w-44 rounded-lg border border-slate-200 bg-white p-1.5 shadow-2xl">
                        <button type="button" onclick="RS.aiStartNewAgentChat(); this.closest('details')?.removeAttribute('open')"
                            class="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-[11px] font-black text-slate-600 hover:bg-slate-50 hover:text-slate-900">
                            <svg class="h-3.5 w-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v6h6M20 20v-6h-6M5 19A9 9 0 0119 5M19 5h-5M19 5v5"/>
                            </svg>
                            <span>New chat</span>
                        </button>
                        <button type="button" onclick="RS.aiArchiveConversation(); this.closest('details')?.removeAttribute('open')"
                            class="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-[11px] font-black text-slate-600 hover:bg-slate-50 hover:text-slate-900">
                            <svg class="h-3.5 w-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M7 8v10h10V8M9 12h6M8 4h8l1 4H7l1-4z"/>
                            </svg>
                            <span>Archive chat</span>
                        </button>
                        <button type="button" onclick="RS.aiToggleArchivePanel(); this.closest('details')?.removeAttribute('open')"
                            class="flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left text-[11px] font-black text-slate-600 hover:bg-slate-50 hover:text-slate-900">
                            <svg class="h-3.5 w-3.5 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 2M4 6h16M5 6v13h14V6M9 3h6"/>
                            </svg>
                            <span>History</span>
                        </button>
                    </div>
                </details>
                <button type="button" onclick="RS.closeAIModal()" title="Close"
                    class="flex h-8 w-8 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700">
                    <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 6l12 12M18 6 6 18"/>
                    </svg>
                </button>
            </div>
        </div>

        <div class="relative min-h-0 flex-1 overflow-hidden">
            <div id="ai-agent-panel" class="flex h-full min-h-0 flex-col bg-white">
                <div id="ai-agent-archive-panel" class="hidden shrink-0 border-b border-slate-100 bg-slate-50 px-4 py-3">
                    <div class="mb-2 flex items-center justify-between gap-3">
                        <div class="text-[10px] font-black uppercase tracking-widest text-slate-400">Saved memory</div>
                        <button type="button" onclick="RS.aiClearConversationArchives()"
                            class="rounded-md border border-slate-200 bg-white px-2 py-1 text-[9px] font-black uppercase tracking-widest text-slate-400 hover:border-red-200 hover:bg-red-50 hover:text-red-500">
                            Clear all
                        </button>
                    </div>
                    <div id="ai-agent-archive-list" class="max-h-40 space-y-2 overflow-y-auto sidebar-scroll"></div>
                </div>
                <div id="ai-agent-messages" class="min-h-0 flex-1 space-y-4 overflow-y-auto bg-white px-5 py-5 sidebar-scroll"></div>
                <div id="ai-agent-session-label" class="pointer-events-none absolute right-5 top-4 font-mono text-[9px] font-bold uppercase tracking-widest text-slate-300"></div>
            </div>

            <div id="ai-result-section" class="hidden flex h-full min-h-0 flex-col gap-3 bg-white p-5">
                <div class="flex items-center justify-between gap-3">
                    <label class="text-[10px] font-black uppercase tracking-widest text-slate-400">AI Output</label>
                    <a id="ai-download-btn" href="#" download
                        class="hidden flex items-center justify-center gap-2 rounded-md border border-sky-100 bg-sky-50 px-3 py-2 text-[10px] font-black text-sky-700 transition-all hover:bg-sky-100">
                        <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4-4 4m0 0-4-4m4 4V4"/>
                        </svg>
                        <span>Download Analysis Report</span>
                    </a>
                </div>
                <pre id="ai-result-content"
                    class="min-h-0 flex-1 overflow-y-auto whitespace-pre-wrap break-words rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-700 sidebar-scroll"></pre>
            </div>

            <div class="pointer-events-none absolute inset-x-4 bottom-3 z-10 space-y-2">
                <div id="ai-error-msg" class="pointer-events-auto hidden rounded-md border border-red-100 bg-red-50 px-3 py-2.5 text-xs text-red-600 shadow-sm"></div>
                <div id="ai-success-msg" class="pointer-events-auto hidden rounded-md border border-emerald-100 bg-emerald-50 px-3 py-2.5 text-xs text-emerald-600 shadow-sm"></div>
                <div id="ai-confirm-section" class="pointer-events-auto hidden grid grid-cols-2 gap-3">
                    <button onclick="RS.aiConfirmCreate()"
                        class="w-full rounded-md bg-emerald-600 py-3 text-xs font-black text-white shadow-lg shadow-emerald-600/15 transition-all hover:bg-emerald-700 active:scale-[0.98]">
                        Create Copy
                    </button>
                    <button onclick="RS.aiConfirmOverwrite()"
                        class="w-full rounded-md bg-amber-500 py-3 text-xs font-black text-white shadow-lg shadow-amber-500/15 transition-all hover:bg-amber-600 active:scale-[0.98]">
                        Overwrite Original
                    </button>
                </div>
            </div>
        </div>

        <div class="shrink-0 border-t border-slate-100 bg-white p-3">
            <label id="ai-prompt-label" class="sr-only">Prompt</label>
            <div class="flex items-end gap-2 rounded-lg border border-slate-200 bg-white p-2 focus-within:ring-2 focus-within:ring-slate-200">
                <div id="ai-agent-attachment-controls" class="shrink-0">
                    <input id="ai-agent-file-input" type="file" multiple
                        accept="image/*,.txt,.md,.markdown,.json,.geojson,.csv,.xml,.log,.py,.js,.ts,.html,.css,.yml,.yaml"
                        class="hidden">
                    <button id="ai-agent-attachment-picker" type="button" title="Attach files"
                        class="flex h-9 w-9 items-center justify-center rounded-md text-slate-400 transition-colors hover:bg-slate-100 hover:text-slate-700">
                        <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.5 6.5l-8.9 8.9a3 3 0 104.2 4.2l9.2-9.2a5 5 0 00-7.1-7.1L4.8 12.4"/>
                        </svg>
                    </button>
                </div>
                <div class="min-w-0 flex-1">
                    <div id="ai-agent-attachment-list" class="mb-2 flex flex-wrap gap-2"></div>
                    <textarea id="ai-prompt-input" rows="2"
                        placeholder="Ask a question or describe a task"
                        class="block max-h-32 min-h-9 w-full resize-none border-0 bg-transparent px-1 py-2 text-xs text-slate-700 placeholder-slate-300 outline-none focus:outline-none"></textarea>
                </div>
                <button id="ai-execute-btn" onclick="RS.aiExecute()"
                    class="inline-flex h-9 min-w-[5.5rem] items-center justify-center gap-2 rounded-md bg-slate-900 px-4 text-xs font-black text-white shadow-lg shadow-slate-900/10 transition-all hover:bg-slate-800 active:scale-[0.98] disabled:cursor-wait disabled:opacity-70">
                    <svg id="ai-spinner" class="hidden h-4 w-4 animate-spin text-white" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z"/>
                    </svg>
                    <span id="ai-execute-label">Send</span>
                </button>
            </div>
        </div>
    </div>
</div>
`;
