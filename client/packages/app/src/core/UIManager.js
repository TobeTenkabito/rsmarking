import { Store } from '../store/index.js';
import { ModalTemplates } from '../../../ui/src/templates/Modals.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { applyTranslations, t } from '../i18n/index.js';

export class UIManager {
    constructor(app) {
        this.app = app;
        this.loadingCount = 0;
        this.currentDetailRaster = null;
    }

    injectModals() {
        const container = document.getElementById('modals-container');
        if (container) {
            container.innerHTML =
                ModalTemplates.indexModal +
                ModalTemplates.extractionModal +
                ModalTemplates.mergeModal +
                ModalTemplates.extractModal +
                ModalTemplates.resampleModal +
                ModalTemplates.preprocessingModal +
                ModalTemplates.demModal +
                ModalTemplates.classificationModal +
                ModalTemplates.calculatorModal +
                ModalTemplates.scriptModal +
                ModalTemplates.aiModal +
                ModalTemplates.exportModal +
                ModalTemplates.clipModal +
                ModalTemplates.changeModal+
                ModalTemplates.conversionModal +
                ModalTemplates.statisticsModal;
        }
        const detailContainer = document.getElementById('detail-panel-container') || document.body;
        const detailDiv = document.createElement('div');
        detailDiv.innerHTML = ModalTemplates.detailPanel;
        detailContainer.appendChild(detailDiv);

        //  Attribute tableEnglish body English
        const attrDiv = document.createElement('div');
        attrDiv.innerHTML = ModalTemplates.attributeTablePanel;
        document.body.appendChild(attrDiv);

        this._initClipModalEvents();
        applyTranslations(document);
    }

    showGlobalLoader(show) {
        const loader = document.getElementById('global-loader');
        if (loader) {
            show ? loader.classList.remove('hidden') : loader.classList.add('hidden');
        }
    }

    /**
     * English
     */
    showGlobalLoading(message = t('ui.loading.default')) {
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
        applyTranslations(loader);
    }

    /**
     * hiddenEnglish
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
     * English
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

        // English
        setTimeout(() => {
            toast.style.transform = 'translateX(120%)';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }

    showDetail(raster) {
        const panel = document.getElementById('detail-panel');
        if (!panel || !raster) return;
        this.currentDetailRaster = raster;
        document.getElementById('detail-title').innerText = raster.file_name;
        document.getElementById('detail-content').innerHTML = ModalComponent.renderDetail(raster);
        applyTranslations(panel);
        panel.classList.remove('hidden');
    }

    hideDetail() {
        this.currentDetailRaster = null;
        document.getElementById('detail-panel')?.classList.add('hidden');
    }

    positionRasterActionMenu(details) {
        if (!details?.open) return;

        document.querySelectorAll('.layer-action-menu[open]').forEach((menu) => {
            if (menu !== details) menu.removeAttribute('open');
        });

        const trigger = details.querySelector('summary');
        const panel = details.querySelector('[data-raster-action-panel]');
        if (!trigger || !panel) return;

        const triggerRect = trigger.getBoundingClientRect();
        const gap = 10;
        const margin = 12;
        const navHeight = 72;
        const panelWidth = panel.offsetWidth || 256;
        const panelHeight = Math.min(panel.scrollHeight || 360, window.innerHeight - margin * 2);

        let left = triggerRect.right + gap;
        if (left + panelWidth > window.innerWidth - margin) {
            left = Math.max(margin, triggerRect.left - panelWidth - gap);
        }

        let top = triggerRect.top - 8;
        if (top + panelHeight > window.innerHeight - margin) {
            top = window.innerHeight - panelHeight - margin;
        }
        top = Math.max(navHeight, top);

        panel.style.left = `${left}px`;
        panel.style.top = `${top}px`;
    }

    _initClipModalEvents() {
        const modal = document.getElementById('clip-modal');
        if (!modal) return;
        modal.addEventListener('change', (e) => {
            if (e.target.name !== 'clip-type') return;
            const val = e.target.value;
            document.getElementById('clip-source-section')
                ?.classList.toggle('hidden', val !== 'vector');
            document.getElementById('clip-layer-section')
                ?.classList.toggle('hidden', val === 'raster');
            document.getElementById('clip-knife-section')
                ?.classList.toggle('hidden', val !== 'layer');
            document.getElementById('clip-raster-info-section')
                ?.classList.toggle('hidden', val === 'layer');});
    }

    openClipModal() {
        const modal = document.getElementById('clip-modal');
        if (!modal) return;
        const defaultRadio = modal.querySelector('input[name="clip-type"][value="raster"]');
        if (defaultRadio) {
            defaultRadio.checked = true;
            defaultRadio.dispatchEvent(new Event('change', {bubbles: true}));
        }
        const rasterInfoEl = document.getElementById('clip-raster-info');
        if (rasterInfoEl) {
            const ids = Store.state.activeLayerIds;
            const activeId = ids.size ? [...ids][0] : null;
            const raster = activeId ? Store.state.rasters.find(r => r.id == activeId) : null;
            rasterInfoEl.innerHTML = raster
                ? `<span class="font-bold text-slate-700">${t('clip.currentRaster')}</span> ${raster.name ?? raster.file_name}`
                : `<span class="text-amber-500">⚠ ${t('clip.noActiveRaster')}</span>`;
        }
        const layers     = Store.state.vectorLayers;
        const layerOpts  = layers.map(l =>
            `<option value="${l.id}">${l.name}</option>`
        ).join('');
        const targetSelect = document.getElementById('clip-vector-layer-select');
        if (targetSelect) {
            targetSelect.innerHTML =
                `<option value="">${t('clip.useActiveLayer')}</option>${layerOpts}`;
        }
        const knifeSelect = document.getElementById('clip-knife-layer-select');
        if (knifeSelect) {
            knifeSelect.innerHTML =
                `<option value="">${t('clip.selectKnifeLayer')}</option>${layerOpts}`;
        }
        applyTranslations(modal);
        modal.classList.remove('hidden');
    }

    closeClipModal() {
    document.getElementById('clip-modal')?.classList.add('hidden');
    // EnglishCancel，EnglishExitEnglish
    this.app.clip?.cancel();
    }

    refreshLanguage() {
        applyTranslations(document);

        if (this.currentDetailRaster && !document.getElementById('detail-panel')?.classList.contains('hidden')) {
            this.showDetail(this.currentDetailRaster);
        }

        if (!document.getElementById('clip-modal')?.classList.contains('hidden')) {
            this.openClipModal();
        }
    }
}
