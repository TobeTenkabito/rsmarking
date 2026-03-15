import { Store } from '../store/index.js';
import { RasterAPI } from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';

export class ScriptModule {
    constructor(app) {
        this.app = app;
        this.currentScript = '';
        this.selectedRasterIds = [];
        this.outputName = '';
        this.isExecuting = false;
        this.scriptHistory = this.loadScriptHistory();
    }

    /**
     * 打开脚本编辑器弹窗
     */
    openScriptEditor() {
        const modal = document.getElementById('script-modal');
        if (!modal) {
            console.error('[ScriptModule] 脚本编辑器弹窗未找到');
            return;
        }

        // 渲染内容
        const content = document.getElementById('script-content');
        content.innerHTML = ModalComponent.renderScriptEditor(
            Store.getRasters(),
            this.selectedRasterIds,
            this.currentScript
        );

        // 显示弹窗
        modal.classList.remove('hidden');

        // 绑定编辑器事件
        this.bindEditorEvents();

        // 加载模板选择器
        this.loadTemplates();

        // 初始化代码高亮（如果有）
        this.initializeCodeHighlight();
    }

    /**
     * 关闭脚本编辑器
     */
    closeScriptEditor() {
        const modal = document.getElementById('script-modal');
        modal?.classList.add('hidden');

        // 保存当前脚本到草稿
        this.saveDraft();
    }

    /**
     * 绑定编辑器事件
     */
    bindEditorEvents() {
        // 脚本内容变化
        const editor = document.getElementById('script-editor-textarea');
        if (editor) {
            editor.addEventListener('input', (e) => {
                this.currentScript = e.target.value;
                this.updateScriptValidation();
            });

            // Tab键支持
            editor.addEventListener('keydown', (e) => {
                if (e.key === 'Tab') {
                    e.preventDefault();
                    const start = editor.selectionStart;
                    const end = editor.selectionEnd;
                    editor.value = editor.value.substring(0, start) + '    ' + editor.value.substring(end);
                    editor.selectionStart = editor.selectionEnd = start + 4;
                    this.currentScript = editor.value;
                }
            });
        }

        // 栅格选择变化
        const rasterCheckboxes = document.querySelectorAll('.script-raster-checkbox');
        rasterCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const id = parseInt(e.target.value);
                if (e.target.checked) {
                    if (!this.selectedRasterIds.includes(id)) {
                        this.selectedRasterIds.push(id);
                    }
                } else {
                    this.selectedRasterIds = this.selectedRasterIds.filter(rid => rid !== id);
                }
                this.updateSelectedCount();
            });
        });

        // 输出文件名
        const outputInput = document.getElementById('script-output-name');
        if (outputInput) {
            outputInput.addEventListener('input', (e) => {
                this.outputName = e.target.value;
            });
        }
    }

    /**
     * Base64 编码（支持 Unicode）
     */
    encodeBase64(str) {
        return btoa(encodeURIComponent(str).replace(/%([0-9A-F]{2})/g, (match, p1) => {
            return String.fromCharCode(parseInt(p1, 16));}));}

    /**
     * Base64 解码（支持 Unicode）
     */
    decodeBase64(str) {
        return decodeURIComponent(atob(str).split('').map(c => {
            return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2);
        }).join(''));
    }

    /**
     * 加载脚本模板
     */
    async loadTemplates() {
        try {
            const templates = await RasterAPI.getScriptTemplates();
            const selector = document.getElementById('script-template-selector');

            if (selector && templates) {
                selector.innerHTML = '<option value="">-- 选择模板 --</option>' +
                    templates.map(t => {
                        // 使用支持 Unicode 的 Base64 编码
                        const encodedCode = this.encodeBase64(t.code);
                        return `<option value="${encodedCode}">${t.name} - ${t.description}</option>`;
                    }).join('');

                selector.addEventListener('change', (e) => {
                    if (e.target.value) {
                        const code = this.decodeBase64(e.target.value);
                        document.getElementById('script-editor-textarea').value = code;
                        this.currentScript = code;
                        this.updateScriptValidation();
                    }
                });
            }
        } catch (error) {
            console.error('[ScriptModule] 加载模板失败:', error);
        }
    }

    /**
     * 执行脚本
     */
    async executeScript() {
        if (this.isExecuting) return;

        // 验证输入
        if (!this.currentScript.trim()) {
            alert('请输入Python脚本');
            return;
        }

        if (this.selectedRasterIds.length === 0) {
            alert('请选择至少一个输入影像');
            return;
        }

        if (!this.outputName.trim()) {
            this.outputName = `script_output_${Date.now()}.tif`;
            document.getElementById('script-output-name').value = this.outputName;
        }

        this.isExecuting = true;
        this.updateExecutionUI(true);

    try {
        // 显示进度
        this.app.ui.showGlobalLoading('正在执行脚本...');

        // 调用API
        const response = await RasterAPI.executeScript(
            this.currentScript,
            this.selectedRasterIds,
            this.outputName
        );

        // 检查HTTP响应状态
        if (!response.ok) {
            const errorText = await response.text();
            console.error('[ScriptModule] HTTP错误:', response.status, errorText);

            // 尝试解析错误信息
            try {
                const errorJson = JSON.parse(errorText);
                throw new Error(errorJson.detail || '服务器错误');
            } catch {
                throw new Error(`服务器错误 (${response.status}): ${errorText}`);
            }
        }

        const result = await response.json();
        console.log('[ScriptModule] 执行结果:', result);

        if (result.status === 'success') {
            this.app.ui.showToast('脚本执行成功', 'success');

            // 显示执行日志（如果有）
            if (result.logs) {
                console.log('[Script Output]:', result.logs);
            }

            // 保存到历史
            this.saveToHistory();

            // 刷新数据
            await this.app.raster.refreshData();

            // 关闭弹窗
            this.closeScriptEditor();
        } else {
            throw new Error(result.error || result.message || '脚本执行失败');
        }
    } catch (error) {
        console.error('[ScriptModule] 执行失败:', error);
        this.app.ui.showToast(`执行失败: ${error.message}`, 'error');
    } finally {
        this.isExecuting = false;
        this.updateExecutionUI(false);
        this.app.ui.hideGlobalLoading();
    }
    }

    /**
     * 更新执行UI状态
     */
    updateExecutionUI(isExecuting) {
        const executeBtn = document.getElementById('script-execute-btn');
        const cancelBtn = document.getElementById('script-cancel-btn');

        if (executeBtn) {
            executeBtn.disabled = isExecuting;
            executeBtn.textContent = isExecuting ? '执行中...' : '执行脚本';
        }

        if (cancelBtn) {
            cancelBtn.disabled = isExecuting;
        }
    }

    /**
     * 验证脚本语法
     */
    updateScriptValidation() {
        const validationDiv = document.getElementById('script-validation');
        if (!validationDiv) return;

        const script = this.currentScript.trim();

        if (!script) {
            validationDiv.innerHTML = '<span class="text-gray-400">请输入脚本</span>';
            return;
        }

        // 基础语法检查
        const issues = [];

        // 检查危险关键字
        const dangerous = ['__import__', 'exec', 'eval', 'compile', '__builtins__'];
        dangerous.forEach(keyword => {
            if (script.includes(keyword)) {
                issues.push(`包含禁止的关键字: ${keyword}`);
            }
        });

        // 检查必要的导入
        if (!script.includes('import rasterio') && !script.includes('from rasterio')) {
            issues.push('建议导入 rasterio 库处理栅格数据');
        }

        // 显示验证结果
        if (issues.length > 0) {
            validationDiv.innerHTML = `
                <div class="text-amber-600 text-xs">
                    <div class="font-bold mb-1">⚠️ 警告:</div>
                    ${issues.map(i => `<div>• ${i}</div>`).join('')}
                </div>
            `;
        } else {
            validationDiv.innerHTML = '<span class="text-green-600 text-xs">✓ 语法检查通过</span>';
        }
    }

    /**
     * 更新选中数量显示
     */
    updateSelectedCount() {
        const countDiv = document.getElementById('script-selected-count');
        if (countDiv) {
            countDiv.textContent = `已选择 ${this.selectedRasterIds.length} 个影像`;
        }
    }

    /**
     * 保存草稿
     */
    saveDraft() {
        if (this.currentScript.trim()) {
            localStorage.setItem('rsmarking_script_draft', JSON.stringify({
                script: this.currentScript,
                rasterIds: this.selectedRasterIds,
                outputName: this.outputName,
                timestamp: Date.now()
            }));
        }
    }

    /**
     * 加载草稿
     */
    loadDraft() {
        try {
            const draft = localStorage.getItem('rsmarking_script_draft');
            if (draft) {
                const data = JSON.parse(draft);
                // 只加载24小时内的草稿
                if (Date.now() - data.timestamp < 24 * 60 * 60 * 1000) {
                    this.currentScript = data.script || '';
                    this.selectedRasterIds = data.rasterIds || [];
                    this.outputName = data.outputName || '';
                    return true;
                }
            }
        } catch (e) {
            console.error('[ScriptModule] 加载草稿失败:', e);
        }
        return false;
    }

    /**
     * 保存到历史记录
     */
    saveToHistory() {
        const history = {
            script: this.currentScript,
            rasterIds: this.selectedRasterIds,
            outputName: this.outputName,
            timestamp: Date.now(),
            id: Date.now().toString()
        };

        this.scriptHistory.unshift(history);
        // 只保留最近20条
        this.scriptHistory = this.scriptHistory.slice(0, 20);

        localStorage.setItem('rsmarking_script_history', JSON.stringify(this.scriptHistory));
    }

    /**
     * 加载历史记录
     */
    loadScriptHistory() {
        try {
            const history = localStorage.getItem('rsmarking_script_history');
            return history ? JSON.parse(history) : [];
        } catch (e) {
            return [];
        }
    }

    /**
     * 显示历史记录
     */
    showHistory() {
        const historyDiv = document.getElementById('script-history');
        if (!historyDiv) return;

        if (this.scriptHistory.length === 0) {
            historyDiv.innerHTML = '<div class="text-gray-400 text-xs text-center py-4">暂无历史记录</div>';
            return;
        }

        historyDiv.innerHTML = this.scriptHistory.map(h => `
            <div class="border rounded p-2 mb-2 hover:bg-gray-50 cursor-pointer" onclick="RS.loadScriptFromHistory('${h.id}')">
                <div class="text-xs font-bold">${h.outputName}</div>
                <div class="text-xs text-gray-500">${new Date(h.timestamp).toLocaleString()}</div>
            </div>
        `).join('');
    }

    /**
     * 从历史加载脚本
     */
    loadFromHistory(historyId) {
        const history = this.scriptHistory.find(h => h.id === historyId);
        if (history) {
            this.currentScript = history.script;
            this.selectedRasterIds = history.rasterIds;
            this.outputName = history.outputName;

            // 更新UI
            const editor = document.getElementById('script-editor-textarea');
            if (editor) editor.value = this.currentScript;

            const outputInput = document.getElementById('script-output-name');
            if (outputInput) outputInput.value = this.outputName;

            this.updateScriptValidation();
            this.updateSelectedCount();
        }
    }

    /**
     * 初始化代码高亮
     */
    initializeCodeHighlight() {
        // 如果引入了代码高亮库（如Prism.js或highlight.js），在这里初始化
        if (window.Prism) {
            Prism.highlightAll();
        }
    }

    /**
     * 清空编辑器
     */
    clearEditor() {
        this.currentScript = '';
        this.selectedRasterIds = [];
        this.outputName = '';

        const editor = document.getElementById('script-editor-textarea');
        if (editor) editor.value = '';

        const outputInput = document.getElementById('script-output-name');
        if (outputInput) outputInput.value = '';

        const checkboxes = document.querySelectorAll('.script-raster-checkbox');
        checkboxes.forEach(cb => cb.checked = false);

        this.updateScriptValidation();
        this.updateSelectedCount();
    }
}
