import { ModalTemplates } from '../../../ui/src/templates/Modals.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';

export class UIManager {
    constructor(app) {
        this.app = app;
    }

    injectModals() {
        const container = document.getElementById('modals-container');
        if (container) {
            container.innerHTML =
                ModalTemplates.indexModal +
                ModalTemplates.extractionModal +
                ModalTemplates.mergeModal +
                ModalTemplates.calculatorModal +
                ModalTemplates.scriptModal +
                ModalTemplates.aiModal  +
                ModalTemplates.exportModal;
        }
        const detailContainer = document.getElementById('detail-panel-container') || document.body;
        const detailDiv = document.createElement('div');
        detailDiv.innerHTML = ModalTemplates.detailPanel;
        detailContainer.appendChild(detailDiv);

        //  属性表抽屉注入到 body 底部
        const attrDiv = document.createElement('div');
        attrDiv.innerHTML = ModalTemplates.attributeTablePanel;
        document.body.appendChild(attrDiv);
    }

    showGlobalLoader(show) {
        const loader = document.getElementById('global-loader');
        if (loader) {
            show ? loader.classList.remove('hidden') : loader.classList.add('hidden');
        }
    }

    /**
     * 显示全局加载提示
     */
    showGlobalLoading(message = '处理中...') {
        this.loadingCount++;

        let loader = document.getElementById('global-loader');
        if (!loader) {
            loader = document.createElement('div');
            loader.id = 'global-loader';
            loader.className = 'fixed top-20 left-1/2 transform -translate-x-1/2 bg-slate-900 text-white px-6 py-3 rounded-full shadow-2xl z-[3000] flex items-center space-x-3';
            document.body.appendChild(loader);
        }

        loader.innerHTML = `
            <svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            <span class="text-sm font-medium">${message}</span>
        `;

        loader.classList.remove('hidden');
    }

    /**
     * 隐藏全局加载提示
     */
    hideGlobalLoading() {
        this.loadingCount = Math.max(0, this.loadingCount - 1);

        if (this.loadingCount === 0) {
            const loader = document.getElementById('global-loader');
            if (loader) {
                loader.classList.add('hidden');
            }
        }
    }

    /**
     * 显示提示消息
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `fixed top-20 right-6 px-6 py-3 rounded-xl shadow-2xl z-[3000] transform translate-x-0 transition-all duration-300`;

        const colors = {
            success: 'bg-green-600 text-white',
            error: 'bg-red-600 text-white',
            warning: 'bg-amber-500 text-white',
            info: 'bg-slate-800 text-white'
        };

        toast.className += ' ' + (colors[type] || colors.info);
        toast.innerHTML = `
            <div class="flex items-center space-x-3">
                <span class="text-sm font-medium">${message}</span>
            </div>
        `;

        document.body.appendChild(toast);

        // 自动消失
        setTimeout(() => {
            toast.style.transform = 'translateX(120%)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    showDetail(raster) {
        const panel = document.getElementById('detail-panel');
        if (!panel || !raster) return;
        document.getElementById('detail-title').innerText = raster.file_name;
        document.getElementById('detail-content').innerHTML = ModalComponent.renderDetail(raster);
        panel.classList.remove('hidden');
    }

    hideDetail() {
        document.getElementById('detail-panel')?.classList.add('hidden');
    }
}