import { RasterAPI } from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { Store } from '../store/index.js';

const RESERVED_TOKENS = new Set([
    'sin','cos','tan','arcsin','arccos','arctan','arctan2',
    'sinh','cosh','tanh','exp','log','log10','sqrt','abs',
    'where','pi','e','expm1','log1p'
]);
const VARIABLE_TOKEN_PATTERN = /\b([A-Za-z][A-Za-z0-9]*(?:_\d+)*)\b/g;

function sameVariables(a, b) {
    return a.length === b.length && a.every((value, index) => value === b[index]);
}


export class CalculatorModule {
    constructor(app) {
        this.app = app;
        this.currentVariables = [];
    }

    openModal() {
        if (Store.state.rasters.length === 0) {
            alert("No imagery in the workspace. Upload data first.");
            return;
        }
        document.getElementById('calculator-modal').classList.remove('hidden');
        this.renderVariableMappers(); // Initialize empty mappings
    }

    closeModal() {
        document.getElementById('calculator-modal')?.classList.add('hidden');
        const expressionInput = document.getElementById('calc-expression-input');
        if (expressionInput) expressionInput.value = '';
        const variablesContainer = document.getElementById('calc-variables-container');
        if (variablesContainer) variablesContainer.innerHTML = '';
    }
    
    handleExpressionChange() {
    const expression = document.getElementById('calc-expression-input').value;
    const baseVarSet = new Set();

    let match;
    VARIABLE_TOKEN_PATTERN.lastIndex = 0;
    while ((match = VARIABLE_TOKEN_PATTERN.exec(expression)) !== null) {
        const token = match[1];
        const parts = token.split('_');
        let splitPos = parts.length;
        for (let i = 0; i < parts.length; i++) {
            if (/^\d+$/.test(parts[i])) { splitPos = i; break; }
        }
        const varName = parts.slice(0, splitPos).join('_');

        if (!varName || RESERVED_TOKENS.has(varName.toLowerCase())) continue;
        baseVarSet.add(varName.toUpperCase());
    }
    const nextVariables = [...baseVarSet].sort();
    if (sameVariables(nextVariables, this.currentVariables)) return;
    this.currentVariables = nextVariables;
    this.renderVariableMappers();
}

    renderVariableMappers() {
        const container = document.getElementById('calc-variables-container');
        if (!container) return;

        // English，English Store English
        container.innerHTML = ModalComponent.renderCalculatorVariables(
            this.currentVariables,
            Store.state.rasters);}

        async execute() {
        const expression = document.getElementById('calc-expression-input').value.trim();
        const newName = document.getElementById('calc-name-input').value.trim();

        if (!expression || !newName) return alert("Enter both the expression and result name.");
        if (this.currentVariables.length === 0) return alert("No valid variables were detected in the expression.");

        // English
        const varMapping = {};
        for (const varName of this.currentVariables) {
            // English：Use querySelector English DOM English
            const selectEl = document.querySelector(`select[data-var="${varName}"]`);

            if (!selectEl || !selectEl.value) {
                return alert(`Select a raster layer for variable ${varName}.`);
            }
            varMapping[`var_${varName}`] = selectEl.value;
        }

        this.app.ui.showGlobalLoader(true);
        try {
            await RasterAPI.runCalculator(expression, varMapping, newName);
            this.closeModal();
            await window.RS.fetchRasters();
        } catch (e) {
            alert("Calculation failed: " + e.message);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    /**
    * English，English
    */
    insertFunction(funcName) {
        const input = document.getElementById('calc-expression-input');
        if (!input) return;
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
    * English
    */
    toggleHelp() {
        const panel = document.getElementById('calc-help-panel');
        panel.classList.toggle('hidden');
    }
}
