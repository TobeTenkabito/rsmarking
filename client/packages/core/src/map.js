export class MapEngine {
    constructor(containerId) {
        console.group("%c[MapEngine] 🏗️ 引擎初始化", "color: #8b5cf6; font-weight: bold;");
        this.containerId = containerId;

        // --- 图层容器 ---
        this.layers = new Map();       // Key: index_id (string), Value: L.TileLayer (栅格瓦片)
        this.vectorLayers = new Map(); // Key: layerId (string), Value: L.GeoJSON (矢量要素)

        this.isReady = false;
        this.tileServiceBase = "http://localhost:8005";
        this.PROJ_DEFS = {
            "EPSG:32651": "+proj=utm +zone=51 +datum=WGS84 +units=m +no_defs",
            "WGS84": "+proj=longlat +datum=WGS84 +no_defs"
        };

        this._initMap();
        console.groupEnd();
    }

    _initMap() {
        if (typeof L === 'undefined') {
            console.error("[MapEngine] ❌ Leaflet 未加载");
            return;
        }
        try {
            this.map = L.map(this.containerId, {zoomControl: false, preferCanvas: true}).setView([35, 105], 4);
            L.control.zoom({ position: 'bottomright' }).addTo(this.map);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap'}).addTo(this.map);this.isReady = true;
                console.log("[MapEngine] ✅ 地图实例已就绪");} catch (e) {
            console.error("[MapEngine] 初始化异常:", e);}}

    _projectToWGS84(boundsArray, sourceCRS = "EPSG:32651") {
        if (typeof proj4 === 'undefined') {console.error("[MapEngine] ❌ 未发现 proj4 库。");return boundsArray;}
        try {
            const [xmin, ymin, xmax, ymax] = boundsArray.map(Number);
            if (Math.abs(xmin) <= 180 && Math.abs(xmax) <= 180 && Math.abs(ymin) <= 90 && Math.abs(ymax) <= 90) {
                return [xmin, ymin, xmax, ymax];
            }
            const fromProj = this.PROJ_DEFS[sourceCRS] || sourceCRS;
            const toProj = this.PROJ_DEFS["WGS84"];
            const sw = proj4(fromProj, toProj, [xmin, ymin]);
            const ne = proj4(fromProj, toProj, [xmax, ymax]);
            console.log(`[MapEngine] 🔄 投影转换成功 [${sourceCRS} -> WGS84]`);
            return [sw[0], sw[1], ne[0], ne[1]];
        } catch (err) {
            console.error("[MapEngine] 坐标转换失败:", err);
            return null;
        }
    }

    _convertBounds(boundsArray) {
        if (!Array.isArray(boundsArray) || boundsArray.length !== 4) {
            return null;
        }
        const wgs84Coords = this._projectToWGS84(boundsArray, "EPSG:32651");
        if (!wgs84Coords) return null;
        const [lngMin, latMin, lngMax, latMax] = wgs84Coords;
        return L.latLngBounds([latMin, lngMin], [latMax, lngMax]);
    }

    async addGeoRasterLayer(raster) {
        const indexId = String(raster.index_id).trim();
        console.group(`%c[MapEngine] ➕ 图层加载: ${indexId}`, "color: #3b82f6;");
        if (!this.isReady) {
            console.groupEnd();
            return false;
        }
        this.removeLayer(indexId);
        const tileUrl = `${this.tileServiceBase}/tile/${indexId}/{z}/{x}/{y}.png?bands=1,2,3`;
        try {
            const layer = L.tileLayer(tileUrl, {
                maxZoom: 18,
                minZoom: 0,
                tileSize: 256,
                crossOrigin: true,
                index_id: indexId
            });
            layer.addTo(this.map);
            this.layers.set(indexId, layer);
            const boundsData = raster.bounds || raster.extent;
            const leafletBounds = this._convertBounds(boundsData);
            if (leafletBounds) {
                this.map.fitBounds(leafletBounds, { padding: [20, 20] });
            }
            console.groupEnd();
            return true;
        } catch (error) {
            console.error("[MapEngine] 渲染异常:", error);
            console.groupEnd();
            return false;
        }
    }

    removeLayer(indexId) {
        if (!indexId) return false;
        const id = String(indexId).trim();
        console.log(`[MapEngine] ➖ 执行移除指令，目标标识: [${id}]`);
        let removed = false;
        const layer = this.layers.get(id);
        if (layer) {
            this.map.removeLayer(layer);
            this.layers.delete(id);
            removed = true;
            console.log(`[MapEngine] ✅ 已成功移除图层引用: ${id}`);
        }
        this.map.eachLayer((l) => {
            const optId = l.options && String(l.options.index_id || "").trim();
            const urlMatch = l._url && l._url.includes(`/tile/${id}/`);
            if (optId === id || urlMatch) {
                this.map.removeLayer(l);
                this.layers.delete(id);
                removed = true;
                console.log(`[MapEngine] 🛡️ 暴力清理成功: ${id}`);
            }
        });
        if (!removed) {
            console.warn(`[MapEngine] ⚠️ 地图上未发现活动图层 [${id}]`);
        }
        return removed;
    }

    fitLayer(indexId, data) {
        const id = String(indexId).trim();
        console.group(`%c[MapEngine] 🎯 触发定位: ${id}`, "color: #f59e0b;");
        if (!this.map) {
            console.groupEnd();
            return;
        }
        let targetBoundsArray = Array.isArray(data) ? data : (data?.bounds || data?.extent || null);
        const leafletBounds = this._convertBounds(targetBoundsArray);
        if (leafletBounds) {
            this.map.invalidateSize();
            this.map.fitBounds(leafletBounds, { padding: [40, 40], animate: true });
        }
        console.groupEnd();
    }

    /**
     * 更新或创建矢量 GeoJSON 图层
     * 适配 MapController.js 中的 this.engine.updateVectorLayer('annotation-layer', geojson)
     */
    updateVectorLayer(layerId, geojson, selectedId) {
    if (!this.isReady || !this.map) return;

    let vectorLayer = this.vectorLayers.get(layerId);

    // 2. 闭包高阶样式函数
    const getFeatureStyle = (feature) => {
        const fid = feature.id || feature.properties?.id;
        const isSelected = fid && fid === selectedId;
        const featureColor = feature.properties?.color || "#4f46e5";
        return {
            color: isSelected ? "#ef4444" : featureColor,
            weight: isSelected ? 3 : 1.5,
            opacity: 1,
            fillColor: featureColor,
            fillOpacity: isSelected ? 0.5 : 0.2,
            className: 'vector-polygon-blend'
        };
    };

    // 3. 首次初始化（加入对上一状态的缓存）
    if (!vectorLayer) {
        console.log(`[MapEngine] 🎨 首次创建图层实例: ${layerId}`);
        vectorLayer = L.geoJSON(geojson, {
            style: getFeatureStyle,
            onEachFeature: (feature, layer) => {
                layer.on('click', (e) => {
                    L.DomEvent.stopPropagation(e);
                    const fid = feature.id || feature.properties?.id;
                    window.dispatchEvent(new CustomEvent('inspect-feature', { detail: { id: fid, feature, layerId } }));
                });
            }
        });
        vectorLayer.addTo(this.map);
        this.vectorLayers.set(layerId, vectorLayer);
        // 记录当前选中的 ID，用于后续局部比对
        vectorLayer._lastSelectedId = selectedId;
        return;
    }

    // 4. 增量更新（Diff 算法）：只删除消失的，只添加新增的
    const newFeaturesMap = new Map();
    const featuresToAdd = [];
    const layerIndexById = new Map();

    // 4.1 建立传入新数据的 Hash 索引
    if (geojson && geojson.features) {
        geojson.features.forEach(f => {
            const fid = f.id || f.properties?.id;
            if (fid) newFeaturesMap.set(fid, f);
        });
    }

    // 4.2 遍历地图上的现有要素，移除不在新数据中的
    vectorLayer.eachLayer(layer => {
        const fid = layer.feature.id || layer.feature.properties?.id;
        if (!newFeaturesMap.has(fid)) {
            vectorLayer.removeLayer(layer); // 视口移出或被删除，卸载它
        } else {
            layer.feature = newFeaturesMap.get(fid); // 更新属性（如颜色改变）
            layerIndexById.set(fid, layer);          // 缓存留下的图层实例
        }
    });

    // 4.3 找出需要新添加到地图的要素
    if (geojson && geojson.features) {
        geojson.features.forEach(f => {
            const fid = f.id || f.properties?.id;
            if (fid && !layerIndexById.has(fid)) {
                featuresToAdd.push(f);
            }
        });
    }

    // 4.4 执行局部添加
    if (featuresToAdd.length > 0) {
        // 更新默认样式闭包，确保新要素直接拿到正确样式
        vectorLayer.options.style = getFeatureStyle;
        vectorLayer.addData(featuresToAdd);
        // 将新加的要素也补充进索引，以备后续样式更新
        vectorLayer.eachLayer(layer => {
            const fid = layer.feature.id || layer.feature.properties?.id;
            if (!layerIndexById.has(fid)) layerIndexById.set(fid, layer);
        });
    }

    // 5. O(1) 级别的局部样式更新（解决选中状态的性能问题）
    const prevSelectedId = vectorLayer._lastSelectedId;
    // 只有当选中项发生变化时，才针对性地修改那两个要素的样式
    if (prevSelectedId !== selectedId) {
        // 恢复之前被选中要素的默认样式
        if (prevSelectedId && layerIndexById.has(prevSelectedId)) {
            layerIndexById.get(prevSelectedId).setStyle(getFeatureStyle);
        }
        // 高亮新被选中的要素
        if (selectedId && layerIndexById.has(selectedId)) {
            const selectedLayer = layerIndexById.get(selectedId);
            selectedLayer.setStyle(getFeatureStyle);
            if (typeof selectedLayer.bringToFront === 'function') selectedLayer.bringToFront();
        }
        vectorLayer._lastSelectedId = selectedId;
    } else if (featuresToAdd.length === 0) {
        // 如果选中项没变，且没有新增几何体，但为了防止外部修改了 color 等属性，
        // 执行一次全量更新。由于 DOM 节点没有增删，这个开销在可接受范围内。
        vectorLayer.setStyle(getFeatureStyle);
    }
}

    syncVisibleLayers(visibleIdsArray) {
        if (!this.isReady) return;
        const visibleSet = new Set(visibleIdsArray);

        // 遍历缓存中的所有图层实例
        for (const [layerId, vectorLayer] of this.vectorLayers.entries()) {
            // 如果某图层不在最新可见列表中，从地图中拔除并销毁缓存
            if (!visibleSet.has(layerId)) {
                this.map.removeLayer(vectorLayer);
                this.vectorLayers.delete(layerId);
            }
        }
    }

    /**
     * 隐藏或移除矢量图层 (当取消选中图层时调用)
     */
    removeVectorLayer(layerId) {
        const layer = this.vectorLayers.get(layerId);
        if (layer) {
            this.map.removeLayer(layer);
            this.vectorLayers.delete(layerId);
            console.log(`[MapEngine] ➖ 移除矢量图层: ${layerId}`);
        }
    }
}
