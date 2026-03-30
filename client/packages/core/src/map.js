export class MapEngine {
    constructor(containerId) {
        console.group("%c[MapEngine] 🏗️ 引擎初始化", "color: #8b5cf6; font-weight: bold;");
        this.containerId = containerId;

        this.layers = new Map();
        this.vectorLayers = new Map();

        this.isReady = false;
        this.tileServiceBase = "http://localhost:8005";
        this.PROJ_DEFS = {
            "EPSG:32651": "+proj=utm +zone=51 +datum=WGS84 +units=m +no_defs",
            "WGS84": "+proj=longlat +datum=WGS84 +no_defs"
        };

        this._initMap();
        console.groupEnd();
        this._cesiumViewer = null;
        this._is3D = false;
    }

    _initMap() {
        if (typeof L === 'undefined') {
            console.error("[MapEngine] ❌ Leaflet 未加载");
            return;
        }
        try {
            this.map = L.map(this.containerId, { zoomControl: false, preferCanvas: true }).setView([35, 105], 4);
            L.control.zoom({ position: 'bottomright' }).addTo(this.map);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap', crossOrigin: 'anonymous'
            }).addTo(this.map);
            this.isReady = true;
            console.log("[MapEngine] ✅ 地图实例已就绪");
        } catch (e) {
            console.error("[MapEngine] 初始化异常:", e);
        }
    }

    _projectToWGS84(boundsArray, sourceCRS = "EPSG:32651") {
        if (typeof proj4 === 'undefined') { console.error("[MapEngine] ❌ 未发现 proj4 库。"); return boundsArray; }
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
        if (!Array.isArray(boundsArray) || boundsArray.length !== 4) return null;
        const wgs84Coords = this._projectToWGS84(boundsArray, "EPSG:32651");
        if (!wgs84Coords) return null;
        const [lngMin, latMin, lngMax, latMax] = wgs84Coords;
        return L.latLngBounds([latMin, lngMin], [latMax, lngMax]);
    }
    async addGeoRasterLayer(raster) {
        const indexId = String(raster.index_id).trim();
        console.group(`%c[MapEngine] ➕ 图层加载: ${indexId}`, "color: #3b82f6;");
        if (!this.isReady) { console.groupEnd(); return false; }

        this.removeLayer(indexId);
        const tileUrl = `${this.tileServiceBase}/tile/${indexId}/{z}/{x}/{y}.png?bands=1,2,3`;
        try {
            const layer = L.tileLayer(tileUrl, {
                maxZoom: 18, minZoom: 0, tileSize: 256,
                crossOrigin: true, index_id: indexId
            });
            layer.addTo(this.map);
            this.layers.set(indexId, layer);
            const boundsData = raster.bounds || raster.extent;
            const leafletBounds = this._convertBounds(boundsData);
            if (leafletBounds) {
                this.map.fitBounds(leafletBounds, { padding: [20, 20] });
            }
            if (this._is3D) {
                this._syncRastersToCesium();
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

        if (!removed) console.warn(`[MapEngine] ⚠️ 地图上未发现活动图层 [${id}]`);

        if (this._is3D) {
            this._syncRastersToCesium();
        }
        return removed;
    }

    fitLayer(indexId, data) {
        const id = String(indexId).trim();
        console.group(`%c[MapEngine] 🎯 触发定位: ${id}`, "color: #f59e0b;");
        if (!this.map) { console.groupEnd(); return; }
        let targetBoundsArray = Array.isArray(data) ? data : (data?.bounds || data?.extent || null);
        const leafletBounds = this._convertBounds(targetBoundsArray);
        if (leafletBounds) {
            this.map.invalidateSize();
            this.map.fitBounds(leafletBounds, { padding: [40, 40], animate: true });
        }
        console.groupEnd();
    }

    updateVectorLayer(layerId, geojson, selectedId) {
        if (!this.isReady || !this.map) return;
        let vectorLayer = this.vectorLayers.get(layerId);
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
        if (!vectorLayer) {
            console.log(`[MapEngine] 🎨 首次创建图层实例: ${layerId}`);
            vectorLayer = L.geoJSON(geojson, {
                style: getFeatureStyle,
                onEachFeature: (feature, layer) => {
                    layer.on('click', (e) => {
                        L.DomEvent.stopPropagation(e);
                        const fid = feature.id || feature.properties?.id;
                        window.dispatchEvent(new CustomEvent('inspect-feature', {
                            detail: { id: fid, feature, layerId }
                        }));
                    });
                }
            });
            vectorLayer.addTo(this.map);
            this.vectorLayers.set(layerId, vectorLayer);
            vectorLayer._lastSelectedId = selectedId;

            if (this._is3D) {
                this._syncSingleVectorToCesium(layerId);
            }
            return;
        }

        const newFeaturesMap = new Map();
        const featuresToAdd = [];
        const layerIndexById = new Map();

        if (geojson && geojson.features) {
            geojson.features.forEach(f => {
                const fid = f.id || f.properties?.id;
                if (fid) newFeaturesMap.set(fid, f);
            });
        }

        vectorLayer.eachLayer(layer => {
            const fid = layer.feature.id || layer.feature.properties?.id;
            if (!newFeaturesMap.has(fid)) {
                vectorLayer.removeLayer(layer);
            } else {
                layer.feature = newFeaturesMap.get(fid);
                layerIndexById.set(fid, layer);
            }
        });

        if (geojson && geojson.features) {
            geojson.features.forEach(f => {
                const fid = f.id || f.properties?.id;
                if (fid && !layerIndexById.has(fid)) featuresToAdd.push(f);
            });
        }

        if (featuresToAdd.length > 0) {
            vectorLayer.options.style = getFeatureStyle;
            vectorLayer.addData(featuresToAdd);
            vectorLayer.eachLayer(layer => {
                const fid = layer.feature.id || layer.feature.properties?.id;
                if (!layerIndexById.has(fid)) layerIndexById.set(fid, layer);
            });
        }

        const prevSelectedId = vectorLayer._lastSelectedId;
        if (prevSelectedId !== selectedId) {
            if (prevSelectedId && layerIndexById.has(prevSelectedId)) {
                layerIndexById.get(prevSelectedId).setStyle(getFeatureStyle);
            }
            if (selectedId && layerIndexById.has(selectedId)) {
                const selectedLayer = layerIndexById.get(selectedId);
                selectedLayer.setStyle(getFeatureStyle);
                if (typeof selectedLayer.bringToFront === 'function') selectedLayer.bringToFront();
            }
            vectorLayer._lastSelectedId = selectedId;
        } else if (featuresToAdd.length === 0) {
            vectorLayer.setStyle(getFeatureStyle);
        }
        if (this._is3D) {
            this._syncSingleVectorToCesium(layerId);
        }
    }

    syncVisibleLayers(visibleIdsArray) {
        if (!this.isReady) return;
        const visibleSet = new Set(visibleIdsArray);

        for (const [layerId, vectorLayer] of this.vectorLayers.entries()) {
            if (!visibleSet.has(layerId)) {
                this.map.removeLayer(vectorLayer);
                this.vectorLayers.delete(layerId);
            }
        }
        if (this._is3D) {
            this._syncVectorsToCesium();
        }
    }

    removeVectorLayer(layerId) {
        const layer = this.vectorLayers.get(layerId);
        if (layer) {
            this.map.removeLayer(layer);
            this.vectorLayers.delete(layerId);
            console.log(`[MapEngine] ➖ 移除矢量图层: ${layerId}`);
        }

        if (this._is3D && this._cesiumViewer) {
            this._cesiumViewer.dataSources.getByName(layerId)
                .forEach(ds => this._cesiumViewer.dataSources.remove(ds));
        }
    }

    _initCesium() {
        if (this._cesiumViewer) return;

        this._cesiumViewer = new Cesium.Viewer('cesium-container', {
            terrainProvider:      new Cesium.EllipsoidTerrainProvider(),
            baseLayerPicker:      false,
            navigationHelpButton: false,
            sceneModePicker:      false,
            geocoder:             false,
            homeButton:           false,
            fullscreenButton:     false,
            animation:            false,
            timeline:             false,
            infoBox:              false,
            selectionIndicator:   false,
            imageryProvider:      false,
        });

        this._cesiumViewer.imageryLayers.addImageryProvider(
            new Cesium.UrlTemplateImageryProvider({
                url: 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
                subdomains: ['a', 'b', 'c'],
                maximumLevel: 19,
                credit: '© OpenStreetMap contributors'
            })
        );

        this._cesiumViewer.cesiumWidget.creditContainer.style.display = 'none';
        console.log('[MapEngine] 🌐 Cesium 3D 引擎已就绪');
    }

    switchTo3D() {
        if (this._is3D) return;

        this._initCesium();

        const center = this.map.getCenter();
        const zoom   = this.map.getZoom();
        const height = 40000000 / Math.pow(2, zoom);

        this._cesiumViewer.camera.flyTo({
            destination: Cesium.Cartesian3.fromDegrees(center.lng, center.lat, height),
            duration: 1.2
        });

        this._syncRastersToCesium();
        this._syncVectorsToCesium();

        document.getElementById('cesium-container').style.display = 'block';
        document.getElementById('map').style.visibility = 'hidden';

        const btn   = document.getElementById('globe-toggle-btn');
        const label = document.getElementById('globe-btn-label');
        if (btn)   btn.classList.add('is-3d');
        if (label) label.textContent = '2D';

        this._is3D = true;
        console.log('[MapEngine] 🌐 已切换到 3D 球形视图');
    }

    switchTo2D() {
        if (!this._is3D) return;

        if (this._cesiumViewer) {
            const pos  = this._cesiumViewer.camera.positionCartographic;
            const lng  = Cesium.Math.toDegrees(pos.longitude);
            const lat  = Cesium.Math.toDegrees(pos.latitude);
            const zoom = Math.round(Math.log2(40000000 / pos.height));
            this.map.setView([lat, lng], Math.max(2, Math.min(zoom, 18)));
        }

        document.getElementById('cesium-container').style.display = 'none';
        document.getElementById('map').style.visibility = 'visible';
        this.map.invalidateSize();

        const btn   = document.getElementById('globe-toggle-btn');
        const label = document.getElementById('globe-btn-label');
        if (btn)   btn.classList.remove('is-3d');
        if (label) label.textContent = '3D';

        this._is3D = false;
        console.log('[MapEngine] 🗺️ 已切换回 2D 平面视图');
    }

    _syncRastersToCesium() {
        if (!this._cesiumViewer) return;

        const layers = this._cesiumViewer.imageryLayers;
        while (layers.length > 1) layers.remove(layers.get(1));

        this.layers.forEach((leafletLayer, indexId) => {
            const tileUrl = `${this.tileServiceBase}/tile/${indexId}/{z}/{x}/{y}.png?bands=1,2,3`;
            layers.addImageryProvider(
                new Cesium.UrlTemplateImageryProvider({
                    url: tileUrl,
                    maximumLevel: 18
                })
            );
        });
    }

    _syncVectorsToCesium() {
        if (!this._cesiumViewer) return;

        this._cesiumViewer.dataSources.removeAll();

        this.vectorLayers.forEach((leafletLayer, layerId) => {
            this._syncSingleVectorToCesium(layerId);
        });
    }

    async _syncSingleVectorToCesium(layerId) {
        if (!this._cesiumViewer) return;

        this._cesiumViewer.dataSources.getByName(layerId)
            .forEach(ds => this._cesiumViewer.dataSources.remove(ds));

        const leafletLayer = this.vectorLayers.get(layerId);
        if (!leafletLayer) return;

        const geojson = leafletLayer.toGeoJSON();
        if (!geojson?.features?.length) return;

        try {
            const dataSource = await Cesium.GeoJsonDataSource.load(geojson, {
                clampToGround: true,
            });

            dataSource.entities.values.forEach(entity => {
                const colorStr = entity.properties?.color?.getValue() ?? '#4f46e5';
                const cesiumColor = Cesium.Color.fromCssColorString(colorStr);

                if (entity.polygon) {
                    entity.polygon.material     = cesiumColor.withAlpha(0.3);
                    entity.polygon.outlineColor  = cesiumColor;
                    entity.polygon.outline       = true;
                }
                if (entity.polyline) {
                    entity.polyline.material = cesiumColor;
                    entity.polyline.width    = 2;
                }
                if (entity.point) {
                    entity.point.color     = cesiumColor;
                    entity.point.pixelSize = 8;
                }
            });

            dataSource.name = layerId;
            this._cesiumViewer.dataSources.add(dataSource);
            console.log(`[MapEngine] 🔷 矢量图层已同步到 Cesium: ${layerId}`);
        } catch (err) {
            console.error(`[MapEngine] ❌ 矢量图层同步失败 [${layerId}]:`, err);
        }
    }
    toggleGlobeView() {
        this._is3D ? this.switchTo2D() : this.switchTo3D();
    }
}