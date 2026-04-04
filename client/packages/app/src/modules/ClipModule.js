import { Store } from '../store/index.js';
import { RasterAPI } from '../api/raster.js';
import { VectorAPI } from '../api/vector.js';
import { boundsToGeometry } from '../utils/geometry.js';

const CLIP_MODE = {
    NONE:   null,
    RASTER: 'raster',
    VECTOR: 'vector',
};

export class ClipModule {
    constructor(app) {
        this.app = app;
        this._clipMode             = CLIP_MODE.NONE;
        this._pendingVectorLayerId = null;
        this._initDrawListener();
    }

    /** 入口 A：手绘多边形裁栅格 */
    startClipRasterByDraw() {
        if (!this._getActiveRasterId()) {
            this.app.ui.showToast('请先在地图上加载一张栅格影像', 'warning');
            return;
        }
        this._enterClipMode(CLIP_MODE.RASTER);
    }

    /** 入口 B-1：用当前激活栅格 bounds 裁矢量 */
    async clipVectorByActiveBounds(targetLayerId) {
        const layerId = targetLayerId ?? Store.state.activeVectorLayerId;
        if (!layerId) {
            this.app.ui.showToast('请先选择一个矢量图层', 'warning');
            return;
        }
        const raster = this._getActiveRasterMeta();
        if (!raster) {
            this.app.ui.showToast('请先在地图上加载一张栅格影像', 'warning');
            return;
        }
        if (!raster.bounds_wgs84) {
            this.app.ui.showToast('当前影像缺少空间范围信息（bounds_wgs84）', 'error');
            return;
        }
        await this._executeClipVector(layerId, boundsToGeometry(raster.bounds_wgs84));
    }

    /** 入口 B-2：手绘多边形裁矢量 */
    startClipVectorByDraw(targetLayerId) {
        const layerId = targetLayerId ?? Store.state.activeVectorLayerId;
        if (!layerId) {
            this.app.ui.showToast('请先选择一个矢量图层', 'warning');
            return;
        }
        this._pendingVectorLayerId = layerId;
        this._enterClipMode(CLIP_MODE.VECTOR);
    }

    /**
     * 入口 C：用一个矢量图层的几何范围裁剪另一个矢量图层
     * @param {string} clipLayerId   作为裁剪刀的图层 id
     * @param {string} targetLayerId 被裁剪的图层 id
     */
    async clipVectorByLayer(clipLayerId, targetLayerId) {
        if (!clipLayerId || !targetLayerId) {
            this.app.ui.showToast('请选择裁剪图层和目标图层', 'warning');
            return;
        }
        if (clipLayerId === targetLayerId) {
            this.app.ui.showToast('裁剪图层和目标图层不能相同', 'warning');
            return;
        }

        this.app.ui.showGlobalLoading('正在获取裁剪图层范围…');
        try {
            const clipFeatures = await this._fetchAllFeatures(clipLayerId);
            if (!clipFeatures.length) {
                this.app.ui.showToast('裁剪图层没有要素', 'warning');
                return;
            }
            const clipGeometry = this._mergeFeaturesToGeometry(clipFeatures);
            this.app.ui.hideGlobalLoading();
            await this._executeClipVector(targetLayerId, clipGeometry);
        } catch (err) {
            console.error('[ClipModule] 图层互裁失败:', err);
            this.app.ui.showToast(`图层互裁失败：${err.message}`, 'error');
            this.app.ui.hideGlobalLoading();
        }
    }

    /** 取消当前裁剪操作 */
    cancel() {
        if (this._clipMode === CLIP_MODE.NONE) return;
        this._exitClipMode();
        this.app.ui.showToast('裁剪操作已取消', 'info');
    }

    async _executeClipRaster(clipGeometry) {
        const rasterId = this._getActiveRasterId();
        const raster   = this._getActiveRasterMeta();
        if (!rasterId || !raster) return;
        const newName = `${raster.name ?? rasterId}_clip_${Date.now()}`;
        this.app.ui.showGlobalLoading('正在裁剪栅格影像…');
        try {
            const result = await RasterAPI.clipRasterByVector(
                rasterId, newName, [clipGeometry], 'EPSG:4326', true, null, false,
                );
            console.log('[ClipModule] 栅格裁剪完成:', result);
            await this.app.raster?.refreshData();
        if (result?.id && this.app.mapController) {
            await this.app.mapController.toggleLayer(result.id);
        }

        this.app.ui.showToast('栅格裁剪完成，新影像已加载', 'success');
    } catch (err) {
        console.error('[ClipModule] 栅格裁剪失败:', err);
        this.app.ui.showToast(`栅格裁剪失败：${err.message}`, 'error');
    } finally {
        this.app.ui.hideGlobalLoading();
    }
}

    async _executeClipVector(layerId, clipGeometry) {
        this.app.ui.showGlobalLoading('正在裁剪矢量要素…');
        try {
            const allFeatures = await this._fetchAllFeatures(layerId);
            if (!allFeatures.length) {
                this.app.ui.showToast('当前图层没有可裁剪的要素', 'warning');
                return;
            }
            const result = await VectorAPI.clipVectorByGeometry(
                clipGeometry, allFeatures, 'EPSG:4326', 'clip',
            );
            if (!result?.features?.length) {
                this.app.ui.showToast('裁剪范围内没有要素', 'warning');
                return;
            }
            await this._saveClipResultToNewLayer(layerId, result.features);
        } catch (err) {
            console.error('[ClipModule] 矢量裁剪失败:', err);
            this.app.ui.showToast(`矢量裁剪失败：${err.message}`, 'error');
        } finally {
            this.app.ui.hideGlobalLoading();
        }
    }

    async _saveClipResultToNewLayer(sourceLayerId, features) {
        const activeProject = Store.state.activeProject;
        if (!activeProject) {
            this.app.ui.showToast('请先选择一个矢量项目', 'warning');
            return;
        }
        const sourceLayer  = Store.state.vectorLayers.find(l => l.id === sourceLayerId);
        const newLayerName = `${sourceLayer?.name ?? sourceLayerId}_clip_${Date.now()}`;

        const newLayer = await VectorAPI.createLayer(activeProject.id, newLayerName, null);
        const payload  = features.map(f => ({
            geometry:   f.geometry,
            properties: {
                ...f.properties,
                clip_source_layer: sourceLayerId,
                clipped_at:        new Date().toISOString(),
            },
        }));
        await VectorAPI.bulkCreateFeatures(newLayer.id, payload);
        console.log(`[ClipModule] 矢量裁剪结果已写入新图层: ${newLayerName}`);

        await this.app.project?.handleSelectProject(activeProject.id);
        if (this.app.mapController?.toggleVectorLayer) {
            this.app.mapController.toggleVectorLayer(newLayer.id);
        }
        this.app.ui.showToast(`裁剪完成，已生成新图层「${newLayerName}」`, 'success');
    }

    _initDrawListener() {
        const map = this.app.mapEngine?.map;
        if (!map) return;

        map.on('draw:created', async (e) => {
            if (this._clipMode === CLIP_MODE.NONE) return;

            const mode           = this._clipMode;
            const pendingLayerId = this._pendingVectorLayerId;
            this._exitClipMode();

            const geometry = e.layer.toGeoJSON().geometry;
            this.app.mapEngine.map.removeLayer(e.layer);

            if (mode === CLIP_MODE.RASTER) {
                await this._executeClipRaster(geometry);
            } else if (mode === CLIP_MODE.VECTOR) {
                await this._executeClipVector(pendingLayerId, geometry);
            }
        });
    }

    _enterClipMode(mode) {
        this._clipMode = mode;
        const map = this.app.mapEngine?.map;
        if (!map) return;

        const color   = '#f59e0b';
        const handler = new L.Draw.Polygon(map, {
            shapeOptions: {
                color, fillColor: color,
                fillOpacity: 0.15, weight: 2, dashArray: '6 4',
            },
        });
        const annotation = this.app.annotation;
        if (annotation) {
            annotation.currentHandler = handler;
            annotation.currentType    = 'polygon';
        }
        handler.enable();

        const label = mode === CLIP_MODE.RASTER ? '栅格裁剪' : '矢量裁剪';
        this.app.ui.showToast(`${label}模式：请在地图上绘制裁剪范围（ESC 取消）`, 'info');
    }

    _exitClipMode() {
        this._clipMode             = CLIP_MODE.NONE;
        this._pendingVectorLayerId = null;
        this.app.annotation?.stopDrawing();
    }

    _getActiveRasterId() {
        const ids = Store.state.activeLayerIds;
        if (!ids.size) return null;
        const activeId = [...ids][0];
        const match = Store.state.rasters.find(r => r.id == activeId);
        return match?.index_id ?? null;  // ← 返回 index_id
    }

    _getActiveRasterMeta() {
        const ids = Store.state.activeLayerIds;
        if (!ids.size) return null;
        const activeId = [...ids][0];
        return Store.state.rasters.find(r => r.id == activeId) ?? null;
    }

    async _fetchAllFeatures(layerId) {
        const fc = await VectorAPI.fetchFeaturesInBbox(layerId, [-180, -90, 180, 90]);
        return fc?.features ?? [];
    }

    /**
     * 将多个 Feature 的几何合并为单个 MultiPolygon
     * 非 Polygon/MultiPolygon 类型的要素会被过滤掉
     */
    _mergeFeaturesToGeometry(features) {
        const polygons = features
            .map(f => f.geometry)
            .filter(g => g?.type === 'Polygon' || g?.type === 'MultiPolygon');

        if (!polygons.length) {
            throw new Error('裁剪图层中没有可用的面要素（Polygon/MultiPolygon）');
        }
        if (polygons.length === 1) return polygons[0];

        const allCoords = polygons.flatMap(g =>
            g.type === 'MultiPolygon' ? g.coordinates : [g.coordinates]
        );
        return { type: 'MultiPolygon', coordinates: allCoords };
    }
}
