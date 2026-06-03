import { RasterAPI } from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { Store } from '../store/index.js';

/**
 * ExtractionModule - EnglishbandsEnglish（English、English、English）
 */
export class ExtractionModule {
    constructor(app) {
        this.app = app;
        this.currentType = null;
        this._contentEl = null;
        this.selectedBandIds = []; // Stores the band IDs selected by the user in order
    }

    /**
     * English
     */
    openModal(type) {
        if (Store.state.rasters.length === 0) {
            alert("Prepare source imagery first.");
            return;
        }

        this.currentType = type;
        this.selectedBandIds = [];
        const content = document.getElementById('extraction-content');
        const bar = document.getElementById('extraction-modal-bar');
        if (!content) return;

        // English
        content.innerHTML = ModalComponent.renderExtractionConfig(type, Store.state.rasters);

        // English：English，English
        if (this._contentEl !== content) {
            this._contentEl = content;
            content.addEventListener('change', (e) => {
                if (e.target && e.target.classList.contains('band-selector')) {
                    this.handleBandSelectionChange(e.target);
                }
            });
        }

        const themeColors = {
            'VEGETATION': '#10b981',
            'WATER': '#3b82f6',
            'BUILDING': '#f59e0b',
            'CLOUD': '#64748b'
        };

        if (bar) bar.style.backgroundColor = themeColors[type] || '#f43f5e';
        document.getElementById('extraction-modal').classList.remove('hidden');
    }

    /**
     * EnglishbandsEnglish：English
     */
    handleBandSelectionChange(target) {
        const container = document.getElementById('dynamic-bands-container');
        if (!container) return;
        const allSelectors = Array.from(container.querySelectorAll('.band-selector'));
        const currentIndex = allSelectors.indexOf(target);

        // such asEnglish，English，English
        if (target.value && currentIndex === allSelectors.length - 1 && allSelectors.length < 5) {
            const nextIndex = allSelectors.length + 1;
            const newField = document.createElement('div');
            newField.className = 'mt-3 animate-fade-in';
            newField.innerHTML = `
                <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">Select band ${nextIndex} (Optional)</label>
                <select class="band-selector w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-blue-500/20">
                    <option value="">-- Select an additional band --</option>
                    ${ModalComponent.renderSelectOptions(Store.state.rasters)}
                </select>
            `;
            container.appendChild(newField);
        }
    }

    closeModal() {
        document.getElementById('extraction-modal')?.classList.add('hidden');
    }

    /**
     * English：Englishbands ID English
     */
    async run() {
        const container = document.getElementById('dynamic-bands-container');
        if (!container) return;
        const selectors = Array.from(container.querySelectorAll('.band-selector'));

        // English ID
        const bandIds = selectors.map(s => s.value).filter(val => val !== "");

        // English：English
        if (bandIds.length < 2) {
            alert("This algorithm requires at least two different bands");
            return;
        }

        const threshold = parseFloat(document.getElementById('extract-threshold-input')?.value || 0);
        const name = document.getElementById('extract-name-input')?.value || `Extract_${Date.now()}`;
        const mode = document.getElementById('extract-mode-input')?.value.trim() || "";
        this.app.ui.showGlobalLoader(true);
        try {
            if (this.currentType === 'VEGETATION') {
                await RasterAPI.extractVegetation(bandIds, name, threshold , mode );
            } else if (this.currentType === 'WATER') {
                await RasterAPI.extractWater(bandIds, name, threshold, mode );
            } else if (this.currentType === 'BUILDING') {
                await RasterAPI.extractBuildings(bandIds, name, threshold, mode);
            } else if (this.currentType === 'CLOUD') {
                await RasterAPI.extractClouds(bandIds, name, threshold, mode);
            }
            else {
                await RasterAPI.extractBuildings(bandIds, name, mode);
            }
            this.closeModal();
            await this.app.raster.refreshData();
        } catch (e) {
            console.error(e);
            alert(`Feature extraction task failed: ${e.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }
}
