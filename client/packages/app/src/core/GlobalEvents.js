import { Store } from '../store/index.js';
import { RasterAPI } from '../api/raster.js';
import { VectorAPI} from "../api/vector.js";
import { t } from '../i18n/index.js';

export class GlobalEvents {
    constructor(app) {
        this.app = app;
        this.layerDragState = null;
        this.layerDropTarget = null;
    }

    bindAll() {
        this.bindDOMDelegation();
        this.bindCustomEvents();
        this.bindMapEvents();
        this.bindKeyboardEvents();
    }

    bindDOMDelegation() {
    // English
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
    this.bindLayerDragAndDrop(listContainer);

    // English
    document.getElementById('raster-upload-input')?.addEventListener('change', async (e) => {
        const files = Array.from(e.target.files || []);
        if (files.length === 0) return;
        this.app.ui.showGlobalLoader(true);
        const results = { success: [], failed: [] };
        for (const file of files) {
            try {
                await RasterAPI.upload(file);
                results.success.push(file.name);
            } catch (err) {
                results.failed.push({ name: file.name, error: err.message });
            }
        }
        if (results.success.length > 0) {
            await this.app.raster.refreshData();
        }
        this.app.ui.showGlobalLoader(false);
        e.target.value = "";
        if (results.failed.length === 0) {
            console.info(`All uploads succeeded (${results.success.length})`);
        } else {
            const failMsg = results.failed.map(f => `• ${f.name}: ${f.error}`).join('\n');
            alert(t('upload.summary.partial', {
                success: results.success.length,
                failed: results.failed.length,
                details: failMsg,
            }));
        }
    });

    // Import Shapefile English
    document.getElementById('shapefile-upload-input')?.addEventListener('change', async (e) => {
        const files = e.target.files;
        if (!files || files.length === 0) return;

        // English
        const names = Array.from(files).map(f => f.name.toLowerCase());
        const required = ['.shp', '.shx', '.dbf'];
        const missing = required.filter(ext => !names.some(n => n.endsWith(ext)));
        if (missing.length > 0) {
            alert(t('upload.alert.missingFiles', { files: missing.join(', ') }));
            e.target.value = "";
            return;
        }

        // English projectId
        const projectId = document.getElementById('shapefile-upload-input').dataset.layerId;
        if (!projectId) {
            alert(t('upload.alert.selectProjectFirst'));
            e.target.value = "";
            return;
        }

        // English .shp File Name（English）English
        const shpFile = Array.from(files).find(f => f.name.toLowerCase().endsWith('.shp'));
        const layerName = shpFile ? shpFile.name.replace(/\.[^.]+$/, '') : 'imported_layer';

        this.app.ui.showGlobalLoader(true);
        try {
            const newLayer = await VectorAPI.createLayer(projectId, layerName);
            const result = await VectorAPI.importShapefile(newLayer.id, files);
            alert(t('upload.alert.importSuccess', {
                imported: result.imported,
                fields: result.fields_registered,
            }));
            await this.app.project.refreshProjects();
            const layers = await VectorAPI.fetchLayers(projectId);
            Store.setVectorLayers(layers)
            const attrTable = this.app?.attributeTable ?? window.app?.attributeTable;
            if (attrTable?.layerId === newLayer.id) {
                await attrTable.refresh();}
        } catch (err) {
            alert(`Import failed: ${err.message}`);
        }});
}

    bindLayerDragAndDrop(container) {
        if (!container) return;

        container.addEventListener('dragstart', (e) => {
            const row = this.getLayerDragRow(e.target);
            if (!row || e.target.closest('button, input, select, textarea, a, summary, .layer-action-menu')) {
                e.preventDefault();
                return;
            }

            this.layerDragState = {
                type: row.dataset.layerDragType,
                id: row.dataset.layerDragId,
                bundleId: row.dataset.layerBundleId,
                projectId: row.dataset.layerProjectId,
            };

            e.dataTransfer.effectAllowed = 'move';
            e.dataTransfer.setData('text/plain', this.layerDragState.id);
            row.classList.add('opacity-50');
        });

        container.addEventListener('dragover', (e) => {
            const target = this.resolveLayerDropTarget(container, e);
            if (!target) {
                this.clearLayerDropMarker();
                if (e.dataTransfer) e.dataTransfer.dropEffect = 'none';
                return;
            }

            e.preventDefault();
            if (e.dataTransfer) e.dataTransfer.dropEffect = 'move';
            this.markLayerDropTarget(target.row, target.position);
        });

        container.addEventListener('dragleave', (e) => {
            if (!container.contains(e.relatedTarget)) this.clearLayerDropMarker();
        });

        container.addEventListener('drop', (e) => {
            const target = this.resolveLayerDropTarget(container, e);
            if (!target) return;

            e.preventDefault();
            const targetId = target.row.dataset.layerDragId;
            const state = this.layerDragState;

            if (state.type === 'raster') {
                Store.reorderRasterLayer(state.id, targetId, target.position);
            } else if (state.type === 'vector') {
                Store.reorderVectorLayer(state.id, targetId, target.position);
            }

            this.clearLayerDragState();
        });

        container.addEventListener('dragend', () => {
            this.clearLayerDragState();
        });
    }

    getLayerDragRow(target) {
        return target?.closest?.('[data-layer-drag-type][data-layer-drag-id]') ?? null;
    }

    resolveLayerDropTarget(container, event) {
        const directRow = this.getLayerDragRow(event.target);
        if (this.isValidLayerDropTarget(directRow)) {
            return {
                row: directRow,
                position: this.getDropPosition(event, directRow),
            };
        }

        const rows = Array.from(container.querySelectorAll('[data-layer-drag-type][data-layer-drag-id]'))
            .filter((row) => this.isValidLayerDropTarget(row));

        if (rows.length === 0) return null;

        for (const row of rows) {
            const rect = row.getBoundingClientRect();
            if (event.clientY < rect.top) {
                return { row, position: 'before' };
            }
            if (event.clientY <= rect.bottom) {
                return { row, position: this.getDropPosition(event, row) };
            }
        }

        return { row: rows[rows.length - 1], position: 'after' };
    }

    isValidLayerDropTarget(row) {
        const state = this.layerDragState;
        if (!row || !state || row.dataset.layerDragId === state.id) return false;
        if (row.dataset.layerDragType !== state.type) return false;

        if (state.type === 'raster') {
            return row.dataset.layerBundleId === state.bundleId;
        }

        if (state.type === 'vector') {
            return row.dataset.layerProjectId === state.projectId;
        }

        return false;
    }

    getDropPosition(event, row) {
        const rect = row.getBoundingClientRect();
        return event.clientY > rect.top + rect.height / 2 ? 'after' : 'before';
    }

    markLayerDropTarget(row, position) {
        if (this.layerDropTarget?.row === row && this.layerDropTarget?.position === position) return;
        this.clearLayerDropMarker();
        row.style.boxShadow = position === 'after'
            ? 'inset 0 -2px 0 #6366f1'
            : 'inset 0 2px 0 #6366f1';
        this.layerDropTarget = { row, position };
    }

    clearLayerDropMarker() {
        if (this.layerDropTarget?.row) {
            this.layerDropTarget.row.style.boxShadow = '';
        }
        this.layerDropTarget = null;
    }

    clearLayerDragState() {
        document
            .querySelectorAll('[data-layer-drag-type].opacity-50')
            .forEach((row) => row.classList.remove('opacity-50'));
        this.clearLayerDropMarker();
        this.layerDragState = null;
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
        // English
        document.addEventListener('keydown', (e) => {
            // Ctrl/Cmd + E English
            if ((e.ctrlKey || e.metaKey) && e.key === 'e') {
                e.preventDefault();
                this.app.script?.openScriptEditor();
            }
            // English，Ctrl/Cmd + Enter Run Script
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                const modal = document.getElementById('script-modal');
                if (modal && !modal.classList.contains('hidden')) {
                    e.preventDefault();
                    this.app.script?.executeScript();
                }
            }
        });
    }

    bindMapEvents() {
        if (this.app.mapEngine && this.app.mapEngine.map) {
            this.app.mapEngine.map.on('click', async (e) => {
                // English
                if (Store.state.spectrumMode) {
                    const { lng, lat } = e.latlng;
                    await this.app.analysis.querySpectrumAt(lng, lat);
                    return; // Stop later logic
                }
                // English：CancelEnglish
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
