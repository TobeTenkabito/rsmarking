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

    // 监听输入框，利用正则动态提取 A, B, C 等变量并生成下拉框
    handleExpressionChange() {
        const expression = document.getElementById('calc-expression-input').value;
        const reservedKeywords = [
        'sin', 'cos', 'tan', 'arcsin', 'arccos', 'arctan', 'arctan2',
        'sinh', 'cosh', 'tanh', 'exp', 'log', 'log10', 'sqrt', 'abs',
        'where', 'pi', 'e', 'expm1', 'log1p'
        ];
        const words = expression.match(/[a-zA-Z]+/g) || [];
        const variables = [...new Set(
            words
                .filter(word => !reservedKeywords.includes(word.toLowerCase())) // 核心修复：排除函数名
                .map(word => word.toUpperCase())
        )].sort();
        this.currentVariables = variables;
        this.renderVariableMappers();}

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
            const selectVal = document.getElementById(`calc-var-${varName}`).value;
            if (!selectVal) return alert(`请为变量 ${varName} 选择对应的栅格图层`);
            varMapping[`var_${varName}`] = selectVal;
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