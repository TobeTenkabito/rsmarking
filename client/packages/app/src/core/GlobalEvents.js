import { Store } from '../store/index.js';
import { RasterAPI } from '../api/raster.js';

export class GlobalEvents {
    constructor(app) {
        this.app = app;
    }

    bindAll() {
        this.bindDOMDelegation();
        this.bindCustomEvents();
        this.bindMapEvents();
        this.bindKeyboardEvents();
    }

    bindDOMDelegation() {
        // 栅格列表委托点击
        const listContainer = document.getElementById('raster-list');
        listContainer?.addEventListener('click', async (e) => {
            const item = e.target.closest('[data-id]');
            if (!item) return;
            const id = item.dataset.id;

            if (e.target.classList.contains('layer-checkbox')) {
                await this.app.mapController.toggleLayer(id);
            } else if (e.target.closest('.btn-delete')) {
                await this.app.raster.handleDelete(id);
            } else if (e.target.closest('.item-info')) {
                const raster = Store.state.rasters.find(r => r.id == id);
                this.app.ui.showDetail(raster);
                await this.app.mapController.focusLayer(id);
            }
        });

        // 上传文件监听
        document.getElementById('raster-upload-input')?.addEventListener('change', async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            this.app.ui.showGlobalLoader(true);
            try {
                await RasterAPI.upload(file);
                await this.app.raster.refreshData();
            } catch (err) {
                alert(`上传失败: ${err.message}`);
            } finally {
                this.app.ui.showGlobalLoader(false);
                e.target.value = "";
            }
        });
    }

    bindCustomEvents() {
        window.addEventListener('inspect-feature', (e) => {
            const featureId = e.detail.id;
            if (!featureId) return;
            Store.setSelectedFeatureId(featureId);

            const delBtn = document.getElementById('btn-delete-feature');
            if (delBtn) delBtn.classList.remove('hidden');

            if (this.app.mapController) {
                this.app.mapController.renderVectorData(Store.state.currentFeatures);
            }
        });
    }

    bindMapEvents() {
        if (this.app.mapEngine && this.app.mapEngine.map) {
            this.app.mapEngine.map.on('click', () => {
                if (Store.state.selectedFeatureId) {
                    Store.setSelectedFeatureId(null);
                    const delBtn = document.getElementById('btn-delete-feature');
                    if (delBtn) delBtn.classList.add('hidden');
                    if (this.app.mapController) {
                        this.app.mapController.renderVectorData(Store.state.currentFeatures);
                    }
                }
            });
        }
    }

    bindKeyboardEvents() {
        document.addEventListener('keydown', async (e) => {
            if ((e.key === 'Delete' || e.key === 'Backspace') && Store.state.selectedFeatureId) {
                await this.app.project.handleDeleteSelectedFeature();
            }
        });
    }
}