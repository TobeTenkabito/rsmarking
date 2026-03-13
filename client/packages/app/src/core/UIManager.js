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
                ModalTemplates.calculatorModal;
        }
        const detailContainer = document.getElementById('detail-panel-container') || document.body;
        const detailDiv = document.createElement('div');
        detailDiv.innerHTML = ModalTemplates.detailPanel;
        detailContainer.appendChild(detailDiv);
    }

    showGlobalLoader(show) {
        const loader = document.getElementById('global-loader');
        if (loader) {
            show ? loader.classList.remove('hidden') : loader.classList.add('hidden');
        }
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