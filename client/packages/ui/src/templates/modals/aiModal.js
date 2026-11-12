import { agentStyles } from './agentStyles.js';
import { agentEnvironmentStyles } from './agentEnvironment.js';

export const aiModal = `
    <div id="ai-modal" class="hidden fixed inset-0 z-[2000] flex items-center justify-center" role="dialog" aria-modal="true" aria-labelledby="ai-dialog-title">
        <style>${agentStyles}${agentEnvironmentStyles}</style>
        <div id="ai-window">
            <aside id="ai-agent-archive-panel" class="ai-history" aria-label="Conversation history">
                <div class="ai-brand">
                    <span class="ai-brand-mark">RS</span>
                    Spatial Assistant
                </div>
                <button type="button" class="ai-new-chat" data-ai-new-chat>
                    <span aria-hidden="true">＋</span>
                    <span>New chat</span>
                </button>
                <input id="ai-history-search" class="ai-history-search" type="search" placeholder="Search conversations" aria-label="Search conversations">
                <div class="ai-history-heading">
                    <span>Recent conversations</span>
                    <div class="ai-history-heading-actions">
                        <button type="button" class="ai-history-import" data-ai-import-chat>Import chat</button>
                        <button type="button" class="ai-icon-button" data-ai-refresh-history aria-label="Refresh history">↻</button>
                    </div>
                </div>
                <input id="ai-history-import-file" type="file" accept=".json,application/json" class="hidden" aria-label="Import chat">
                <nav id="ai-agent-archive-list" aria-label="Saved conversations"></nav>
                <button id="ai-save-status" class="ai-status" type="button" data-ai-save-chat aria-live="polite">Conversations save automatically</button>
                <div class="ai-environment-launcher">
                    <button type="button" class="ai-environment-button" data-ai-environment aria-label="Agent environment" title="Agent environment">
                        <span aria-hidden="true">⚙</span>
                    </button>
                    <span class="ai-environment-label">Agent environment</span>
                </div>
            </aside>
            <main class="ai-main">
                <header class="ai-header">
                    <div>
                        <h2 id="ai-dialog-title">AI Spatial Assistant</h2>
                        <div id="ai-mode-caption" class="ai-caption">Agent mode</div>
                    </div>
                    <div class="ai-header-actions">
                        <details id="ai-context-panel" class="ai-settings">
                            <summary>Settings</summary>
                            <div class="ai-settings-card">
                                <label class="ai-setting">
                                    Task Mode
                                    <select id="ai-mode-select">
                                        <option value="agent">Agent mode</option>
                                        <option value="analyze">Analysis Mode</option>
                                        <option value="modify">Modify Mode</option>
                                    </select>
                                </label>
                                <label id="ai-permission-control" class="ai-setting">
                                    Agent permission
                                    <select id="ai-permission-select">
                                        <option value="read_only">Read only</option>
                                        <option value="safe">Safe actions</option>
                                        <option value="standard" selected>Standard</option>
                                        <option value="full_control">Full control</option>
                                    </select>
                                </label>
                                <label id="ai-execution-control" class="ai-setting">
                                    Agent workflow
                                    <select id="ai-execution-select">
                                        <option value="collaborative" selected>Plan, execute and verify</option>
                                        <option value="single">Direct agent</option>
                                    </select>
                                </label>
                                <p class="ai-setting-note">Collaboration shares one budget and allows one automatic repair.</p>
                                <div id="ai-permission-banner" class="ai-setting-note"></div>
                                <label class="ai-setting-check">
                                    <input id="ai-task-autonomy" type="checkbox" checked>
                                    Automatically complete task steps
                                </label>
                                <p class="ai-setting-note">Allow necessary processing and new outputs. Existing data changes follow the selected permission.</p>
                                <label class="ai-setting-check">
                                    <input id="ai-use-tools" type="checkbox" checked>
                                    Use project tools
                                </label>
                                <label class="ai-setting-check">
                                    <input id="ai-workspace-context" type="checkbox" checked>
                                    Include workspace context
                                </label>
                                <label class="ai-setting-check">
                                    <input id="ai-archive-memory" type="checkbox">
                                    Use other saved chats as memory
                                </label>
                                <label class="ai-setting">
                                    Target Data
                                    <select id="ai-target-select"></select>
                                </label>
                                <div id="ai-context-summary" class="ai-setting-note">Optional in agent mode</div>
                                <label class="ai-setting">
                                    Data Type
                                    <select id="ai-datatype-select">
                                        <option value="raster">Raster Imagery</option>
                                        <option value="vector">Vector Layer</option>
                                    </select>
                                </label>
                                <label class="ai-setting">
                                    Output Language
                                    <select id="ai-language-select">
                                        <option value="zh">中文</option>
                                        <option value="en">English</option>
                                        <option value="ja">日本語</option>
                                        <option value="es">Español</option>
                                    </select>
                                </label>
                            </div>
                        </details>
                        <details id="ai-function-panel" class="ai-settings hidden">
                            <summary>Tools</summary>
                            <div class="ai-settings-card">
                                <div id="ai-function-status"></div>
                                <button type="button" onclick="RS.aiReloadFunctions()">Refresh</button>
                                <div id="ai-function-buttons"></div>
                                <div id="ai-function-detail" class="hidden">
                                    <div id="ai-function-summary"></div>
                                    <label for="ai-function-args-input">Arguments JSON</label>
                                    <textarea id="ai-function-args-input" rows="6" class="w-full border rounded p-2"></textarea>
                                    <button type="button" onclick="RS.aiResetFunctionArgs()">Reset Args</button>
                                    <button id="ai-function-run-btn" type="button" onclick="RS.aiRunSelectedFunction()">Run Function</button>
                                </div>
                            </div>
                        </details>
                        <button type="button" class="ai-icon-button" onclick="RS.closeAIModal()" aria-label="Close" title="Close">×</button>
                    </div>
                </header>
                <div class="ai-body">
                    <section id="ai-agent-panel">
                        <div id="ai-agent-messages" role="log" aria-label="Conversation" aria-live="polite" aria-relevant="additions text"></div>
                    </section>
                    <section id="ai-result-section" class="hidden">
                        <a id="ai-download-btn" href="#" download class="hidden">
                            <span>Download Analysis Report</span>
                        </a>
                        <div id="ai-result-content"></div>
                    </section>
                </div>
                <div id="ai-error-msg" class="ai-toast hidden" role="alert"></div>
                <div id="ai-success-msg" class="ai-toast hidden" role="status"></div>
                <div id="ai-confirm-section" class="hidden px-5 py-2">
                    <button type="button" onclick="RS.aiConfirmCreate()">Create Copy</button>
                    <button type="button" onclick="RS.aiConfirmOverwrite()">Overwrite Original</button>
                </div>
                <footer class="ai-composer">
                    <div class="ai-composer-box">
                        <div id="ai-agent-attachment-list" class="flex flex-wrap gap-2 mb-2"></div>
                        <label id="ai-prompt-label" for="ai-prompt-input" class="sr-only">Message</label>
                        <textarea id="ai-prompt-input" rows="2" placeholder="Ask a question or describe a task" aria-describedby="ai-keyboard-hint"></textarea>
                        <div class="ai-composer-controls">
                            <div class="ai-composer-left">
                                <div id="ai-agent-attachment-controls">
                                    <input id="ai-agent-file-input" type="file" multiple accept="image/png,image/jpeg,image/webp,image/gif,.txt,.md,.markdown,.json,.geojson,.csv,.xml,.log,.py,.js,.ts,.html,.css,.yml,.yaml" class="hidden">
                                    <button id="ai-agent-attachment-picker" type="button" class="ai-icon-button" title="Attach files" aria-label="Attach files">＋</button>
                                </div>
                                <span id="ai-keyboard-hint">Ctrl + Enter for a new line</span>
                            </div>
                            <button id="ai-execute-btn" type="button" onclick="RS.aiExecute()">
                                <span id="ai-spinner" class="hidden animate-spin" aria-hidden="true">◌</span>
                                <span id="ai-execute-label">Send</span>
                                <span aria-hidden="true">↑</span>
                            </button>
                        </div>
                    </div>
                    <div class="ai-composer-footer">
                        <span>AI can make mistakes. Review important results.</span>
                        <select id="ai-send-mode" aria-label="Send shortcut">
                            <option value="enter">Enter to send</option>
                            <option value="ctrl-enter">Ctrl + Enter to send</option>
                        </select>
                    </div>
                </footer>
            </main>
        </div>
    </div>
`;
