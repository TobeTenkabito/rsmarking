import { RasterAPI } from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { Store } from '../store/index.js';


export class CalculatorModule {
    constructor(app) {
        this.app = app;
        this.currentVariables = [];
    }

    openModal() {
        if (Store.state.rasters.length === 0) {
            alert("工作站暂无影像，请先上传数据");
            return;
        }
        document.getElementById('calculator-modal').classList.remove('hidden');
        this.renderVariableMappers(); // 初始化空映射
    }

    closeModal() {
        document.getElementById('calculator-modal').classList.add('hidden');
        document.getElementById('calc-expression-input').value = '';
        document.getElementById('calc-variables-container').innerHTML = '';
    }
    
    handleExpressionChange() {
    const expression = document.getElementById('calc-expression-input').value;
    const RESERVED = new Set([
        'sin','cos','tan','arcsin','arccos','arctan','arctan2',
        'sinh','cosh','tanh','exp','log','log10','sqrt','abs',
        'where','pi','e','expm1','log1p'
    ]);
    const tokenPattern = /\b([A-Za-z][A-Za-z0-9]*(?:_\d+)*)\b/g;
    const baseVarSet = new Set();

    let match;
    while ((match = tokenPattern.exec(expression)) !== null) {
        const token = match[1];
        const parts = token.split('_');
        let splitPos = parts.length;
        for (let i = 0; i < parts.length; i++) {
            if (/^\d+$/.test(parts[i])) { splitPos = i; break; }
        }
        const varName = parts.slice(0, splitPos).join('_');

        if (!varName || RESERVED.has(varName.toLowerCase())) continue;
        baseVarSet.add(varName.toUpperCase());
    }
    this.currentVariables = [...baseVarSet].sort();
    this.renderVariableMappers();
}

    renderVariableMappers() {
        const container = document.getElementById('calc-variables-container');
        if (!container) return;

        // 使用组件进行渲染，传入当前变量和 Store 里的数据
        container.innerHTML = ModalComponent.renderCalculatorVariables(
            this.currentVariables,
            Store.state.rasters);}

        async execute() {
        const expression = document.getElementById('calc-expression-input').value.trim();
        const newName = document.getElementById('calc-name-input').value.trim();

        if (!expression || !newName) return alert("请完整填写表达式和结果名称");
        if (this.currentVariables.length === 0) return alert("表达式中未检测到有效变量");

        // 组装动态映射参数
        const varMapping = {};
        for (const varName of this.currentVariables) {
            // 修改点：使用 querySelector 结合属性选择器来获取 DOM 节点
            const selectEl = document.querySelector(`select[data-var="${varName}"]`);

            if (!selectEl || !selectEl.value) {
                return alert(`请为变量 ${varName} 选择对应的栅格图层`);
            }
            varMapping[`var_${varName}`] = selectEl.value;
        }

        this.app.ui.showGlobalLoader(true);
        try {
            await RasterAPI.runCalculator(expression, varMapping, newName);
            this.closeModal();
            await window.RS.fetchRasters();
        } catch (e) {
            alert("计算失败: " + e.message);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    /**
    * 在输入框光标处插入函数名，并自动聚焦
    */
    insertFunction(funcName) {
        const input = document.getElementById('calc-expression-input');
        const start = input.selectionStart;
        const end = input.selectionEnd;
        const text = input.value;
        const insertText = funcName === 'where' ? 'where(,,)' : `${funcName}()`;
        input.value = text.substring(0, start) + insertText + text.substring(end);
        const newCursorPos = start + (funcName === 'where' ? 6 : funcName.length + 1);
        input.setSelectionRange(newCursorPos, newCursorPos);
        input.focus();
        this.handleExpressionChange();}

    /**
    * 切换帮助面板的显示状态
    */
    toggleHelp() {
        const panel = document.getElementById('calc-help-panel');
        panel.classList.toggle('hidden');
    }
}