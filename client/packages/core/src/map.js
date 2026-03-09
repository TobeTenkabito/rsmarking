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
        if (!this.isReady) return;

        let vectorLayer = this.vectorLayers.get(layerId);

        // 每次调用都生成最新的 style 函数，确保拿到最新的 selectedId
        const dynamicStyle = function (feature) {
            // 同时兼容根节点 id 和属性里的 id
            const fid = feature.id || feature.properties?.id;
            const isSelected = fid && fid === selectedId;
            const featureColor = feature.properties?.color || "#4f46e5";

            return {
                color: isSelected ? "#ef4444" : featureColor,  // 边框颜色
                weight: isSelected ? 4 : 2,                    // 边框粗细
                opacity: 1,                                    // 边框透明度
                fillColor: featureColor,                       // 填充颜色
                fillOpacity: 0.3,                              // 填充透明度
                className: 'vector-polygon-blend'              // 混合模式类名
            };
        };

        if (!vectorLayer) {
            // 第一次加载：创建图层并配置样式
            console.log(`[MapEngine] 🎨 初始化矢量图层: ${layerId}`);
            vectorLayer = L.geoJSON(geojson, {
                style: dynamicStyle,
                // 绑定点击事件，供UI侧拉取属性面板
                onEachFeature: (feature, layer) => {
                    layer.on('click', (e) => {
                        L.DomEvent.stopPropagation(e); // 阻止事件冒泡到地图
                        // 派发全局事件给 UI 层监听
                        const fid = feature.id || feature.properties?.id;
                        window.dispatchEvent(new CustomEvent('inspect-feature', {detail: { id: fid, feature }}));
                    });
                }
            });

            vectorLayer.addTo(this.map);
            this.vectorLayers.set(layerId, vectorLayer);
        } else {
            // 图层已存在：清空旧数据，注入新数据
            console.log(`[MapEngine] 🔄 更新矢量图层: ${layerId}, 要素数量: ${geojson.features?.length || 0}`);
            vectorLayer.clearLayers();
            if (geojson && geojson.features && geojson.features.length > 0) {
                // 将带有最新 selectedId 闭包的函数覆写回去，解决选中不变色的 Bug
                vectorLayer.options.style = dynamicStyle;
                vectorLayer.addData(geojson);
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