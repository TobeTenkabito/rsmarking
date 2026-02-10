export class MapEngine {
    constructor(containerId) {
        console.group("%c[MapEngine] 🏗️ 引擎初始化", "color: #8b5cf6; font-weight: bold;");
        this.containerId = containerId;
        this.layers = new Map(); // Key: index_id (string), Value: L.TileLayer
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
            this.map = L.map(this.containerId, {
                zoomControl: false,
                preferCanvas: true
            }).setView([35, 105], 4);

            L.control.zoom({ position: 'bottomright' }).addTo(this.map);

            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '© OpenStreetMap'
            }).addTo(this.map);

            this.isReady = true;
            console.log("[MapEngine] ✅ 地图实例已就绪");
        } catch (e) {
            console.error("[MapEngine] 初始化异常:", e);
        }
    }
    _projectToWGS84(boundsArray, sourceCRS = "EPSG:32651") {
        if (typeof proj4 === 'undefined') {
            console.error("[MapEngine] ❌ 未发现 proj4 库。");
            return boundsArray;
        }
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
}