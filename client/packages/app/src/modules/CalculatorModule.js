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
        // 提取所有连续的英文字母作为变量名，并去重
        const matches = expression.match(/[a-zA-Z]+/g) || [];
        const uniqueVars = [...new Set(matches)].filter(v => v.toUpperCase() !== 'NAN');

        this.currentVariables = uniqueVars;
        this.renderVariableMappers();
    }

    renderVariableMappers() {
        const container = document.getElementById('calc-variables-container');
        container.innerHTML = ModalComponent.renderCalculatorVariables(this.currentVariables, Store.state.rasters);
    }

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
}