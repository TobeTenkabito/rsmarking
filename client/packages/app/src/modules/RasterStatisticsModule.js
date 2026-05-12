import { RasterAPI } from '../api/raster.js';
import { Store } from '../store/index.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { applyTranslations } from '../i18n/index.js';


export class RasterStatisticsModule {
    constructor(app) {
        this.app = app;
        this.currentRasterId = null;
        this.currentStats = null;
        this.activeBandIndex = null;
    }

    async open(rasterId) {
        if (!rasterId) {
            this.app.ui.showToast('Select a raster first', 'warning');
            return;
        }

        const raster = this._findRaster(rasterId);
        this.currentRasterId = raster?.index_id ?? rasterId;
        this.currentStats = null;
        this.activeBandIndex = null;

        const modal = document.getElementById('raster-statistics-modal');
        const content = document.getElementById('raster-statistics-content');
        const subtitle = document.getElementById('raster-statistics-subtitle');
        if (!modal || !content) return;

        if (subtitle) subtitle.textContent = raster?.file_name ?? `Raster ${this.currentRasterId}`;
        content.innerHTML = ModalComponent.renderRasterStatisticsLoading(raster?.file_name);
        modal.classList.remove('hidden');
        applyTranslations(modal);

        await this.refresh();
    }

    close() {
        document.getElementById('raster-statistics-modal')?.classList.add('hidden');
    }

    async refresh() {
        if (!this.currentRasterId) return;

        const content = document.getElementById('raster-statistics-content');
        const raster = this._findRaster(this.currentRasterId);
        if (content) {
            content.innerHTML = ModalComponent.renderRasterStatisticsLoading(raster?.file_name);
        }

        try {
            const stats = await RasterAPI.getStatistics(this.currentRasterId, {
                bins: 32,
                maxSize: 768,
            });
            this.currentStats = stats;
            this.activeBandIndex = stats?.bands?.[0]?.index ?? null;
            this._render();
        } catch (error) {
            console.error('[RasterStatisticsModule] failed:', error);
            if (content) {
                content.innerHTML = ModalComponent.renderRasterStatisticsError(error.message);
                applyTranslations(content);
            }
        }
    }

    selectBand(bandIndex) {
        this.activeBandIndex = Number(bandIndex);
        this._render();
    }

    _render() {
        const content = document.getElementById('raster-statistics-content');
        if (!content || !this.currentStats) return;
        content.innerHTML = ModalComponent.renderRasterStatistics(
            this.currentStats,
            this.activeBandIndex,
        );
        applyTranslations(content);
    }

    _findRaster(rasterId) {
        return Store.state.rasters.find((raster) =>
            String(raster.index_id) === String(rasterId) ||
            String(raster.id) === String(rasterId)
        );
    }
}
