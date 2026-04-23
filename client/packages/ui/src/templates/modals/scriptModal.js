export const scriptModal =`
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
    `;