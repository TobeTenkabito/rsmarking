import { RasterAPI } from '../api/raster.js';
import { Store } from '../store/index.js';

export class ExportModule {
    constructor(app) {
        this.app = app;
        this._html2canvasLoaded = false;
        this._html2canvasPromise = null;
        this._uiBound = false;
        this._previewSeq = 0;
    }

    _getMap() {
        const engine = this.app?.mapEngine;
        return engine?.map ?? engine;
    }

    _getMapEngine() {
        return this.app?.mapEngine ?? null;
    }

    _getCesiumViewer() {
        const engine = this._getMapEngine();
        return engine?.getCesiumViewer?.() ?? null;
    }

    _is3DExport() {
        const engine = this._getMapEngine();
        return Boolean(engine?.is3DMode?.() && this._getCesiumViewer());
    }

    openModal() {
        const modal = document.getElementById('export-modal');
        if (!modal) return;
        modal.classList.remove('hidden');
        this._bindUIEvents();
        this._syncFilenameExt();
        this._syncJpegQualityVisibility();
        this._syncExportModeUI();
    }

    closeModal() {
        document.getElementById('export-modal')?.classList.add('hidden');
    }

    async refreshPreview() {
        const previewSeq = ++this._previewSeq;
        const placeholder = document.getElementById('export-preview-placeholder');
        const canvas      = document.getElementById('export-preview-canvas');
        const loader      = document.getElementById('export-preview-loader');
        if (!canvas) return;

        if (this._getSelectedFormat() === 'file') {
            loader?.classList.add('hidden');
            canvas.classList.add('hidden');
            if (placeholder) {
                placeholder.classList.remove('hidden');
                placeholder.innerHTML = `
                    <div class="text-2xl mb-1">GIS</div>
                    <p class="text-[10px] text-slate-400 px-4">
                        GIS file mode exports data packages usable in QGIS / ArcGIS.
                    </p>`;
            }
            return;
        }

        loader?.classList.remove('hidden');
        placeholder?.classList.add('hidden');
        canvas.classList.add('hidden');

        try {
            const opts       = this._collectOptions();
            const fullCanvas = await this._renderToCanvas(opts);
            if (previewSeq !== this._previewSeq) return;
            const container  = document.getElementById('export-preview-container');
            const ctx        = canvas.getContext('2d');

            canvas.width  = container.clientWidth  * window.devicePixelRatio;
            canvas.height = container.clientHeight * window.devicePixelRatio;
            canvas.style.width  = container.clientWidth  + 'px';
            canvas.style.height = container.clientHeight + 'px';
            ctx.drawImage(fullCanvas, 0, 0, canvas.width, canvas.height);
            canvas.classList.remove('hidden');
        } catch (e) {
            if (previewSeq !== this._previewSeq) return;
            console.error('[ExportModule] Preview failed:', e);
            if (placeholder) {
                placeholder.classList.remove('hidden');
                placeholder.innerHTML =
                    `<p class="text-[10px] text-red-400">Preview failed: ${e.message}</p>`;
            }
        } finally {
            if (previewSeq === this._previewSeq) loader?.classList.add('hidden');
        }
    }

    async executeExport() {
        const btn     = document.getElementById('export-execute-btn');
        const spinner = document.getElementById('export-spinner');
        if (!btn) return;

        btn.disabled = true;
        spinner?.classList.remove('hidden');

        try {
            const opts = this._collectOptions();
            if (opts.format === 'file') {
                await this._exportGISFile(opts);
            } else if (opts.format === 'svg') {
                await this._exportSVG(opts);
            } else {
                const canvas = await this._renderToCanvas(opts);
                this._downloadCanvas(canvas, opts);
            }
        } catch (e) {
            console.error('[ExportModule] Export failed:', e);
            alert(`Export failed：${e.message}`);
        } finally {
            btn.disabled = false;
            spinner?.classList.add('hidden');
        }
    }


    async _renderToCanvas(opts) {
        if (this._is3DExport()) {
            return this._renderCesiumToCanvas(opts);
        }

        const map   = this._getMap();
        const mapEl = map?.getContainer();
        if (!mapEl) throw new Error('Map instance is not initialized');

        const W = mapEl.clientWidth  * opts.scale;
        const H = mapEl.clientHeight * opts.scale;
        const showFrameLabels = opts.includeGraticule && opts.includeFrameLabels;

        // English（Englishlatitude）
        const MARGIN = showFrameLabels ? Math.round(36 * opts.scale) : 0;

        const output = document.createElement('canvas');
        output.width  = W + MARGIN * 2;   // Leave MARGIN on the left and right
        output.height = H + MARGIN * 2;   // Leave MARGIN on the top and bottom
        const ctx = output.getContext('2d');

        // English（English）
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, output.width, output.height);

        // ① English（English）
        ctx.save();
        ctx.translate(MARGIN, MARGIN);

        if (opts.includeBasemap) {
            const basemapCanvas = await this._captureBasemap(mapEl);
            if (basemapCanvas) {
                ctx.drawImage(basemapCanvas, 0, 0, W, H);
            } else {
                ctx.fillStyle = '#e8f4f8';
                ctx.fillRect(0, 0, W, H);
            }
        } else {
            ctx.fillStyle = '#f8fafc';
            ctx.fillRect(0, 0, W, H);
        }

        // ② Raster imagery layers
        if (opts.includeRasters) {
            this._drawRasterLayers(ctx, mapEl, W, H);
        }

        // ③ Vector annotation layers
        if (opts.includeVectors) {
            await this._drawVectorLayers(ctx, mapEl, W, H);
        }

        // ④ English（English，English）
        if (opts.includeGraticule) {
            this._drawGraticuleLines(ctx, map, W, H, opts.scale, opts.graticuleStyle);
        }

        // ⑤ English
        if (opts.includeDecorations) {
            this._drawDecorations(ctx, W, H, opts.scale);
        }

        ctx.restore();

        // ⑥ EnglishlatitudeEnglish（English translate English，English）
        if (showFrameLabels) {
            this._drawGraticuleFrame(ctx, map, W, H, MARGIN, opts.scale);
        }

        return output;
    }


    async _renderCesiumToCanvas(opts) {
        const viewer = this._getCesiumViewer();
        const sourceCanvas = viewer?.scene?.canvas ?? viewer?.canvas;
        const container = viewer?.container ?? document.getElementById('cesium-container') ?? sourceCanvas;
        if (!viewer || !sourceCanvas || !container) throw new Error('3D map is not initialized');

        const cssW = container.clientWidth || sourceCanvas.clientWidth || sourceCanvas.width;
        const cssH = container.clientHeight || sourceCanvas.clientHeight || sourceCanvas.height;
        const W = Math.max(1, Math.round(cssW * opts.scale));
        const H = Math.max(1, Math.round(cssH * opts.scale));

        const output = document.createElement('canvas');
        output.width = W;
        output.height = H;
        const ctx = output.getContext('2d');

        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, W, H);

        await this._withCesiumExportVisibility(viewer, opts, async () => {
            viewer.resize?.();
            await this._waitForCesiumFrame(viewer);
            ctx.drawImage(sourceCanvas, 0, 0, W, H);
        });

        if (opts.includeGraticule) {
            this._drawCesiumGraticule(ctx, viewer, W, H, opts.scale, opts.graticuleStyle, opts.includeFrameLabels);
        }

        if (opts.includeDecorations) {
            this._drawCesiumDecorations(ctx, viewer, W, H, opts.scale);
        }

        return output;
    }


    async _withCesiumExportVisibility(viewer, opts, callback) {
        const imagery = viewer.imageryLayers;
        const imageryState = [];
        const dataSourceState = [];

        if (imagery) {
            for (let i = 0; i < imagery.length; i++) {
                const layer = imagery.get(i);
                imageryState.push({ layer, show: layer.show });
                layer.show = i === 0 ? opts.includeBasemap : opts.includeRasters;
            }
        }

        if (viewer.dataSources) {
            for (let i = 0; i < viewer.dataSources.length; i++) {
                const dataSource = viewer.dataSources.get(i);
                dataSourceState.push({ dataSource, show: dataSource.show });
                dataSource.show = opts.includeVectors;
            }
        }

        try {
            return await callback();
        } finally {
            imageryState.forEach(({ layer, show }) => {
                layer.show = show;
            });
            dataSourceState.forEach(({ dataSource, show }) => {
                dataSource.show = show;
            });
            viewer.scene?.requestRender?.();
        }
    }


    async _waitForCesiumFrame(viewer) {
        viewer.scene?.requestRender?.();
        await new Promise(resolve => requestAnimationFrame(resolve));
        await new Promise(resolve => requestAnimationFrame(resolve));
    }


    /**
     * English（English）
     */
    _niceLatLngInterval(map) {
        const bounds = map.getBounds();
        return this._niceLatLngIntervalFromBbox([
            bounds.getWest(),
            bounds.getSouth(),
            bounds.getEast(),
            bounds.getNorth()
        ]);
    }

    _niceLatLngIntervalFromBbox(bbox) {
        const [west, south, east, north] = bbox ?? [-180, -90, 180, 90];
        const spanLng = Number.isFinite(east - west) ? Math.abs(east - west) : 360;
        const spanLat = Number.isFinite(north - south) ? Math.abs(north - south) : 180;
        const span = Math.max(spanLng, spanLat, 0.01);

        // English：English 4~6 English
        const raw = span / 5;
        const candidates = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5,
                            1, 2, 5, 10, 15, 20, 30, 45, 60];
        let best = candidates[0];
        for (const c of candidates) {
            best = c;
            if (c >= raw) break;
        }
        return best;
    }

    /**
     * EnglishlatitudeEnglish（English scale）
     */
    _latlngToPixel(map, lat, lng, mapEl, scale) {
        const point = map.latLngToContainerPoint([lat, lng]);
        return { x: point.x * scale, y: point.y * scale };
    }

    _getCesiumViewBbox(viewer) {
        const engineBbox = this._getMapEngine()?.getViewBbox?.();
        if (Array.isArray(engineBbox) && engineBbox.length === 4) {
            const bbox = engineBbox.map(Number);
            if (bbox.every(Number.isFinite)) return this._normalizeBbox(bbox);
        }

        const CesiumRef = window.Cesium;
        const rectangle = viewer?.camera?.computeViewRectangle?.(viewer.scene?.globe?.ellipsoid);
        if (!CesiumRef || !rectangle) return [-180, -90, 180, 90];

        return this._normalizeBbox([
            CesiumRef.Math.toDegrees(rectangle.west),
            CesiumRef.Math.toDegrees(rectangle.south),
            CesiumRef.Math.toDegrees(rectangle.east),
            CesiumRef.Math.toDegrees(rectangle.north)
        ]);
    }

    _normalizeBbox(bbox) {
        const west = this._clamp(Number(bbox[0]), -180, 180);
        const south = this._clamp(Number(bbox[1]), -90, 90);
        const east = this._clamp(Number(bbox[2]), -180, 180);
        const north = this._clamp(Number(bbox[3]), -90, 90);
        if (!Number.isFinite(west + south + east + north)) return [-180, -90, 180, 90];
        if (east < west) return [-180, south, 180, north];
        return [west, south, east, north];
    }

    _buildGraticuleValues(min, max, interval, lower, upper) {
        const lo = Math.max(min, lower);
        const hi = Math.min(max, upper);
        if (!Number.isFinite(lo) || !Number.isFinite(hi) || hi < lo) return [];

        const start = Math.floor(lo / interval) * interval;
        const end = Math.ceil(hi / interval) * interval;
        const values = [];
        for (let v = start; v <= end + interval * 0.001; v += interval) {
            const value = Number(v.toFixed(8));
            if (value >= lower - 1e-9 && value <= upper + 1e-9) values.push(value);
        }
        return values;
    }

    _drawCesiumGraticule(ctx, viewer, W, H, scale, style, includeLabels) {
        const bbox = this._getCesiumViewBbox(viewer);
        const interval = this._niceLatLngIntervalFromBbox(bbox);
        const west = this._clamp(bbox[0] - interval, -180, 180);
        const south = this._clamp(bbox[1] - interval, -90, 90);
        const east = this._clamp(bbox[2] + interval, -180, 180);
        const north = this._clamp(bbox[3] + interval, -90, 90);
        const lngValues = this._buildGraticuleValues(west, east, interval, -180, 180);
        const latValues = this._buildGraticuleValues(south, north, interval, -90, 90);
        const occluder = this._createCesiumOccluder(viewer);
        const labelLines = { lng: [], lat: [] };

        ctx.save();
        ctx.strokeStyle = 'rgba(40, 72, 132, 0.62)';
        ctx.lineWidth = Math.max(0.8, 1.05 * scale);
        ctx.setLineDash(style === 'dashed' ? [6 * scale, 5 * scale] : []);

        lngValues.forEach((lng) => {
            const points = this._sampleCesiumGraticuleLine(
                viewer, 'lng', lng, south, north, interval, scale, occluder
            );
            this._drawProjectedLine(ctx, points, W, H, scale);
            if (includeLabels) labelLines.lng.push({ value: lng, points });
        });

        latValues.forEach((lat) => {
            const points = this._sampleCesiumGraticuleLine(
                viewer, 'lat', lat, west, east, interval, scale, occluder
            );
            this._drawProjectedLine(ctx, points, W, H, scale);
            if (includeLabels) labelLines.lat.push({ value: lat, points });
        });

        ctx.restore();

        if (includeLabels) {
            this._drawCesiumGraticuleLabels(ctx, labelLines, W, H, scale);
        }
    }

    _sampleCesiumGraticuleLine(viewer, axis, fixedValue, start, end, interval, scale, occluder) {
        const span = Math.abs(end - start);
        const sampleCount = Math.min(220, Math.max(24, Math.ceil(span / Math.max(interval / 6, 0.25))));
        const points = [];

        for (let i = 0; i <= sampleCount; i++) {
            const t = sampleCount === 0 ? 0 : i / sampleCount;
            const value = start + (end - start) * t;
            const lng = axis === 'lng' ? fixedValue : value;
            const lat = axis === 'lng' ? value : fixedValue;
            points.push(this._projectCesiumLngLat(viewer, lng, lat, scale, occluder));
        }

        return points;
    }

    _createCesiumOccluder(viewer) {
        const CesiumRef = window.Cesium;
        try {
            if (!CesiumRef?.EllipsoidalOccluder || !viewer?.scene?.globe?.ellipsoid) return null;
            return new CesiumRef.EllipsoidalOccluder(
                viewer.scene.globe.ellipsoid,
                viewer.camera.positionWC
            );
        } catch {
            return null;
        }
    }

    _projectCesiumLngLat(viewer, lng, lat, scale, occluder = null) {
        const CesiumRef = window.Cesium;
        if (!CesiumRef?.Cartesian3) return null;
        const cartesian = CesiumRef.Cartesian3.fromDegrees(lng, lat, 0);
        return this._projectCesiumCartesian(viewer, cartesian, scale, occluder);
    }

    _projectCesiumCartesian(viewer, cartesian, scale, occluder = null) {
        const CesiumRef = window.Cesium;
        if (!CesiumRef?.SceneTransforms || !cartesian) return null;
        if (occluder && !occluder.isPointVisible(cartesian)) return null;

        const point = CesiumRef.SceneTransforms.wgs84ToWindowCoordinates(viewer.scene, cartesian);
        if (!point) return null;

        const x = point.x * scale;
        const y = point.y * scale;
        if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
        return { x, y };
    }

    _drawProjectedLine(ctx, points, W, H, scale) {
        const maxJump = Math.max(W, H) * 0.75;
        const hardLimit = Math.max(W, H) * 4;
        let started = false;
        let previous = null;

        ctx.beginPath();
        points.forEach((point) => {
            const valid = point &&
                point.x > -hardLimit && point.x < W + hardLimit &&
                point.y > -hardLimit && point.y < H + hardLimit;

            if (!valid) {
                if (started) ctx.stroke();
                ctx.beginPath();
                started = false;
                previous = null;
                return;
            }

            if (previous && Math.hypot(point.x - previous.x, point.y - previous.y) > maxJump) {
                if (started) ctx.stroke();
                ctx.beginPath();
                started = false;
            }

            if (!started) {
                ctx.moveTo(point.x, point.y);
                started = true;
            } else {
                ctx.lineTo(point.x, point.y);
            }
            previous = point;
        });

        if (started) ctx.stroke();
    }

    _drawCesiumGraticuleLabels(ctx, labelLines, W, H, scale) {
        const lngStride = Math.max(1, Math.ceil(labelLines.lng.length / 9));
        const latStride = Math.max(1, Math.ceil(labelLines.lat.length / 9));

        labelLines.lng.forEach((line, index) => {
            if (index % lngStride !== 0) return;
            const point = this._pickVisibleLabelPoint(line.points, W, H, 'bottom');
            if (point) this._drawMapLabel(ctx, this._formatDeg(line.value, 'lng'), point.x, point.y - 10 * scale, W, H, scale);
        });

        labelLines.lat.forEach((line, index) => {
            if (index % latStride !== 0) return;
            const point = this._pickVisibleLabelPoint(line.points, W, H, 'right');
            if (point) this._drawMapLabel(ctx, this._formatDeg(line.value, 'lat'), point.x - 10 * scale, point.y, W, H, scale);
        });
    }

    _pickVisibleLabelPoint(points, W, H, prefer) {
        let best = null;
        for (const point of points) {
            if (!point || point.x < 0 || point.x > W || point.y < 0 || point.y > H) continue;
            if (!best) {
                best = point;
                continue;
            }
            if (prefer === 'bottom' && point.y > best.y) best = point;
            else if (prefer === 'right' && point.x > best.x) best = point;
        }
        return best;
    }

    _drawMapLabel(ctx, text, x, y, W, H, scale) {
        const fontSize = Math.max(10, 10 * scale);
        const padX = 4 * scale;
        const padY = 2 * scale;
        const radius = 4 * scale;

        ctx.save();
        ctx.font = `600 ${fontSize}px -apple-system, "PingFang SC", sans-serif`;
        const metrics = ctx.measureText(text);
        const width = metrics.width + padX * 2;
        const height = fontSize + padY * 2;
        const cx = this._clamp(x, width / 2 + 6 * scale, W - width / 2 - 6 * scale);
        const cy = this._clamp(y, height / 2 + 6 * scale, H - height / 2 - 6 * scale);

        ctx.fillStyle = 'rgba(255,255,255,0.82)';
        ctx.strokeStyle = 'rgba(30,41,59,0.16)';
        ctx.lineWidth = Math.max(0.6, 0.7 * scale);
        ctx.beginPath();
        ctx.roundRect(cx - width / 2, cy - height / 2, width, height, radius);
        ctx.fill();
        ctx.stroke();

        ctx.fillStyle = '#1e293b';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(text, cx, cy);
        ctx.restore();
    }

    _drawGraticuleLines(ctx, map, W, H, scale, style) {
    const interval = this._niceLatLngInterval(map);
    const bounds   = map.getBounds();

    // ✅ English interval，English
    // ✅ English floor/ceil English：west English，east English
    const lngStart = Math.floor(bounds.getWest()  / interval) * interval;
    const lngEnd   = Math.ceil( bounds.getEast()  / interval) * interval;
    const latStart = Math.floor(bounds.getSouth() / interval) * interval;
    const latEnd   = Math.ceil( bounds.getNorth() / interval) * interval;

    ctx.save();
    ctx.strokeStyle = 'rgba(80, 100, 160, 0.55)';
    ctx.lineWidth   = Math.max(0.6, 0.8 * scale);
    ctx.setLineDash(style === 'dashed' ? [6 * scale, 5 * scale] : []);

    // ── English（English）：EnglishlatitudeEnglish x，y English 0 English H ──
    for (let lng = lngStart; lng <= lngEnd + 1e-9; lng += interval) {
        const pt = map.latLngToContainerPoint([map.getCenter().lat, lng]);
        const x  = pt.x * scale;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, H);
        ctx.stroke();
    }

    // ── English（English）：English y，x English 0 English W ──
    for (let lat = latStart; lat <= latEnd + 1e-9; lat += interval) {
        const pt = map.latLngToContainerPoint([lat, map.getCenter().lng]);
        const y  = pt.y * scale;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(W, y);
        ctx.stroke();
    }

    ctx.restore();
}


    _drawGraticuleFrame(ctx, map, W, H, MARGIN, scale) {
    const interval = this._niceLatLngInterval(map);
    const bounds   = map.getBounds();

    // ✅ English _drawGraticuleLines English
    const lngStart = Math.floor(bounds.getWest()  / interval) * interval;
    const lngEnd   = Math.ceil( bounds.getEast()  / interval) * interval;
    const latStart = Math.floor(bounds.getSouth() / interval) * interval;
    const latEnd   = Math.ceil( bounds.getNorth() / interval) * interval;

    const fontSize = Math.max(9, 9 * scale);
    const tickLen  = 5 * scale;

    ctx.save();

    // ── EnglishRectangle ──
    ctx.strokeStyle = '#334155';
    ctx.lineWidth   = Math.max(1, 1.2 * scale);
    ctx.setLineDash([]);
    ctx.strokeRect(MARGIN, MARGIN, W, H);

    ctx.font      = `${fontSize}px -apple-system, "PingFang SC", sans-serif`;
    ctx.fillStyle = '#1e293b';

    // ── English（English）──
    ctx.textAlign = 'center';
    for (let lng = lngStart; lng <= lngEnd + 1e-9; lng += interval) {
        const pt = map.latLngToContainerPoint([map.getCenter().lat, lng]);
        const px = pt.x * scale + MARGIN;

        // English
        if (px < MARGIN || px > MARGIN + W) continue;

        const label = this._formatDeg(lng, 'lng');

        // English
        ctx.beginPath();
        ctx.moveTo(px, MARGIN);
        ctx.lineTo(px, MARGIN - tickLen);
        ctx.stroke();
        ctx.textBaseline = 'bottom';
        ctx.fillText(label, px, MARGIN - tickLen - 2 * scale);

        // English
        ctx.beginPath();
        ctx.moveTo(px, MARGIN + H);
        ctx.lineTo(px, MARGIN + H + tickLen);
        ctx.stroke();
        ctx.textBaseline = 'top';
        ctx.fillText(label, px, MARGIN + H + tickLen + 2 * scale);
    }

    // ── latitudeEnglish（English）──
    for (let lat = latStart; lat <= latEnd + 1e-9; lat += interval) {
        const pt = map.latLngToContainerPoint([lat, map.getCenter().lng]);
        const py = pt.y * scale + MARGIN;

        if (py < MARGIN || py > MARGIN + H) continue;

        const label = this._formatDeg(lat, 'lat');

        // English
        ctx.textAlign    = 'right';
        ctx.textBaseline = 'middle';
        ctx.beginPath();
        ctx.moveTo(MARGIN, py);
        ctx.lineTo(MARGIN - tickLen, py);
        ctx.stroke();
        ctx.fillText(label, MARGIN - tickLen - 3 * scale, py);

        // English
        ctx.textAlign = 'left';
        ctx.beginPath();
        ctx.moveTo(MARGIN + W, py);
        ctx.lineTo(MARGIN + W + tickLen, py);
        ctx.stroke();
        ctx.fillText(label, MARGIN + W + tickLen + 3 * scale, py);
    }

    ctx.restore();
}


    /**
     * EnglishlatitudeEnglish "120°E" / "30°N" English
     */
    _formatDeg(val, type) {
        const normalized = Math.abs(Number(val) || 0);
        let degValue = Math.floor(normalized);
        let minutes = Math.round((normalized - degValue) * 60);
        if (minutes === 60) {
            degValue += 1;
            minutes = 0;
        }
        const suffix = type === 'lng'
            ? (val >= 0 ? 'E' : 'W')
            : (val >= 0 ? 'N' : 'S');
        const value = minutes > 0
            ? `${degValue}\u00b0${String(minutes).padStart(2, '0')}'`
            : `${degValue}\u00b0`;
        return `${value}${suffix}`;
        /*
        const abs = Math.abs(val);
        const deg = Math.floor(abs);
        const min = Math.round((abs - deg) * 60);
        let str = min > 0 ? `${deg}°${String(min).padStart(2,'0')}′` : `${deg}°`;
        if (type === 'lng') str += val >= 0 ? 'E' : 'W';
        else                str += val >= 0 ? 'N' : 'S';
        return str;
        */
    }


    async _captureBasemap(mapEl) {
        const tileCanvas = this._extractTileImages(mapEl);
        if (tileCanvas) return tileCanvas;

        try {
            await this._loadHtml2Canvas();
            return await window.html2canvas(mapEl, {
                useCORS:        true,
                allowTaint:     false,
                logging:        false,
                ignoreElements: el =>
                    el.classList.contains('leaflet-control-container')
            });
        } catch {
            return null;
        }
    }

    _extractTileImages(mapEl) {
        const W       = mapEl.clientWidth;
        const H       = mapEl.clientHeight;
        const mapRect = mapEl.getBoundingClientRect();
        const tiles   = mapEl.querySelectorAll(
            '.leaflet-tile-pane img.leaflet-tile'
        );
        if (!tiles.length) return null;

        const out = document.createElement('canvas');
        out.width  = W;
        out.height = H;
        const ctx = out.getContext('2d');

        tiles.forEach(img => {
            if (!img.complete || img.naturalWidth === 0) return;
            try {
                const r = img.getBoundingClientRect();
                ctx.drawImage(img,
                    r.left - mapRect.left,
                    r.top  - mapRect.top,
                    r.width, r.height
                );
            } catch { /* Skip cross-origin tiles */ }
        });

        return out;
    }


    _drawRasterLayers(ctx, mapEl, W, H) {
        const mapRect = mapEl.getBoundingClientRect();
        const mW      = mapEl.clientWidth;
        const mH      = mapEl.clientHeight;

        mapEl.querySelectorAll(
            '.leaflet-overlay-pane canvas, .leaflet-image-layer'
        ).forEach(el => {
            try {
                const r = el.getBoundingClientRect();
                ctx.drawImage(el,
                    (r.left - mapRect.left) / mW * W,
                    (r.top  - mapRect.top)  / mH * H,
                    r.width  / mW * W,
                    r.height / mH * H
                );
            } catch (e) {
                console.warn('[ExportModule] Raster draw skipped:', e.message);
            }
        });
    }

    async _drawVectorLayers(ctx, mapEl, W, H) {
        const svgEl = mapEl.querySelector('.leaflet-overlay-pane svg');
        if (!svgEl) return;

        const mapRect = mapEl.getBoundingClientRect();
        const svgRect = svgEl.getBoundingClientRect();
        const clone   = svgEl.cloneNode(true);

        clone.setAttribute('width',   W);
        clone.setAttribute('height',  H);
        clone.setAttribute('viewBox',
            `${svgRect.left - mapRect.left} ` +
            `${svgRect.top  - mapRect.top} ` +
            `${mapRect.width} ${mapRect.height}`
        );

        const blob = new Blob(
            [new XMLSerializer().serializeToString(clone)],
            { type: 'image/svg+xml;charset=utf-8' }
        );
        const url = URL.createObjectURL(blob);

        await new Promise((resolve, reject) => {
            const img  = new Image();
            img.onload = () => {
                ctx.drawImage(img, 0, 0, W, H);
                URL.revokeObjectURL(url);
                resolve();
            };
            img.onerror = reject;
            img.src = url;
        });
    }


    _drawDecorations(ctx, W, H, scale) {
        const pad = 16 * scale;
        ctx.save();
        this._drawScaleBar(ctx, W, H, pad, scale);
        this._drawNorthArrow(ctx, W, pad, scale);
        this._drawTimestamp(ctx, W, H, pad, scale);
        ctx.restore();
    }

    _drawCesiumDecorations(ctx, viewer, W, H, scale) {
        const pad = 16 * scale;
        ctx.save();
        this._drawCesiumScaleBar(ctx, viewer, W, H, pad, scale);
        this._drawNorthArrow(ctx, W, pad, scale, this._getCesiumNorthVector(viewer, W, H, scale));
        this._drawTimestamp(ctx, W, H, pad, scale);
        ctx.restore();
    }

    _drawScaleBar(ctx, W, H, pad, scale) {
        const map = this._getMap();
        if (!map) return;
        const center = map.getCenter();
        const zoom   = map.getZoom();

        const mpp = 40075016.686 *
            Math.abs(Math.cos(center.lat * Math.PI / 180)) /
            Math.pow(2, zoom + 8);

        const targetPx  = 100 * scale;
        const niceM     = this._niceNumber(mpp * targetPx);
        const barPx     = (niceM / mpp) * scale;

        const x    = pad;
        const y    = H - pad - 20 * scale;
        const barH = 5 * scale;

        ctx.fillStyle = 'rgba(255,255,255,0.85)';
        ctx.beginPath();
        ctx.roundRect(x - 6*scale, y - 14*scale,
            barPx + 12*scale, 26*scale, 4*scale);
        ctx.fill();

        ctx.fillStyle = '#334155';
        ctx.fillRect(x, y, barPx / 2, barH);
        ctx.fillStyle = '#94a3b8';
        ctx.fillRect(x + barPx / 2, y, barPx / 2, barH);

        const label = niceM >= 1000
            ? `${(niceM / 1000).toFixed(0)} km`
            : `${niceM.toFixed(0)} m`;
        ctx.font      = `bold ${10 * scale}px -apple-system, sans-serif`;
        ctx.fillStyle = '#334155';
        ctx.textAlign = 'center';
        ctx.fillText(label, x + barPx / 2, y - 4 * scale);
    }

    _drawCesiumScaleBar(ctx, viewer, W, H, pad, scale) {
        const targetPx = 100 * scale;
        const y = H - pad - 20 * scale;
        const distance = this._measureCesiumScreenDistance(
            viewer,
            pad / scale,
            y / scale,
            (pad + targetPx) / scale,
            y / scale
        ) ?? this._measureCesiumScreenDistance(
            viewer,
            W / (2 * scale),
            H / (2 * scale),
            W / (2 * scale) + targetPx / scale,
            H / (2 * scale)
        );

        if (!Number.isFinite(distance) || distance <= 0) return;

        const niceM = this._niceNumber(distance);
        const barPx = this._clamp((niceM / distance) * targetPx, 36 * scale, 180 * scale);
        const x = pad;
        const barH = 5 * scale;

        ctx.fillStyle = 'rgba(255,255,255,0.86)';
        ctx.beginPath();
        ctx.roundRect(x - 6 * scale, y - 14 * scale,
            barPx + 12 * scale, 26 * scale, 4 * scale);
        ctx.fill();

        ctx.fillStyle = '#334155';
        ctx.fillRect(x, y, barPx / 2, barH);
        ctx.fillStyle = '#94a3b8';
        ctx.fillRect(x + barPx / 2, y, barPx / 2, barH);

        const label = niceM >= 1000
            ? `${(niceM / 1000).toFixed(0)} km`
            : `${niceM.toFixed(0)} m`;
        ctx.font = `bold ${10 * scale}px -apple-system, sans-serif`;
        ctx.fillStyle = '#334155';
        ctx.textAlign = 'center';
        ctx.fillText(label, x + barPx / 2, y - 4 * scale);
    }

    _measureCesiumScreenDistance(viewer, x1, y1, x2, y2) {
        const CesiumRef = window.Cesium;
        if (!CesiumRef?.Cartesian2) return null;

        const first = this._pickCesiumGlobe(viewer, new CesiumRef.Cartesian2(x1, y1));
        const second = this._pickCesiumGlobe(viewer, new CesiumRef.Cartesian2(x2, y2));
        if (!first || !second) return null;

        try {
            const start = CesiumRef.Cartographic.fromCartesian(first);
            const end = CesiumRef.Cartographic.fromCartesian(second);
            const geodesic = new CesiumRef.EllipsoidGeodesic(start, end);
            return geodesic.surfaceDistance;
        } catch {
            return null;
        }
    }

    _pickCesiumGlobe(viewer, screenPosition) {
        try {
            const scene = viewer.scene;
            const ray = viewer.camera.getPickRay(screenPosition);
            return scene.globe.pick(ray, scene) ??
                viewer.camera.pickEllipsoid(screenPosition, scene.globe.ellipsoid);
        } catch {
            return null;
        }
    }

    _getCesiumNorthVector(viewer, W, H, scale) {
        const CesiumRef = window.Cesium;
        if (!CesiumRef?.Cartesian2) return this._northVectorFromCameraHeading(viewer);

        const center = this._pickCesiumGlobe(
            viewer,
            new CesiumRef.Cartesian2(W / (2 * scale), H / (2 * scale))
        );
        if (!center) return this._northVectorFromCameraHeading(viewer);

        try {
            const cartographic = CesiumRef.Cartographic.fromCartesian(center);
            const lng = CesiumRef.Math.toDegrees(cartographic.longitude);
            const lat = CesiumRef.Math.toDegrees(cartographic.latitude);
            const northLat = this._clamp(lat + 0.05, -89.95, 89.95);
            const p0 = CesiumRef.SceneTransforms.wgs84ToWindowCoordinates(viewer.scene, center);
            const p1 = CesiumRef.SceneTransforms.wgs84ToWindowCoordinates(
                viewer.scene,
                CesiumRef.Cartesian3.fromDegrees(lng, northLat, 0)
            );
            if (!p0 || !p1) return this._northVectorFromCameraHeading(viewer);

            const dx = p1.x - p0.x;
            const dy = p1.y - p0.y;
            const length = Math.hypot(dx, dy);
            if (length < 1e-3) return this._northVectorFromCameraHeading(viewer);
            return { x: dx / length, y: dy / length };
        } catch {
            return this._northVectorFromCameraHeading(viewer);
        }
    }

    _northVectorFromCameraHeading(viewer) {
        const heading = viewer?.camera?.heading ?? 0;
        return {
            x: Math.sin(heading),
            y: -Math.cos(heading)
        };
    }

    _drawNorthArrow(ctx, W, pad, scale, northVector = { x: 0, y: -1 }) {
        const cx = W - pad - 18 * scale;
        const cy = pad + 30 * scale;
        const r  = 14 * scale;

        ctx.fillStyle = 'rgba(255,255,255,0.9)';
        ctx.beginPath();
        ctx.arc(cx, cy, r + 4 * scale, 0, Math.PI * 2);
        ctx.fill();

        const angle = Math.atan2(northVector.y, northVector.x) + Math.PI / 2;
        ctx.save();
        ctx.translate(cx, cy);
        ctx.rotate(angle);

        ctx.fillStyle = '#1e293b';
        ctx.beginPath();
        ctx.moveTo(0, -r);
        ctx.lineTo(-6 * scale, 4 * scale);
        ctx.lineTo(0, 0);
        ctx.closePath();
        ctx.fill();

        ctx.fillStyle = '#cbd5e1';
        ctx.beginPath();
        ctx.moveTo(0, r);
        ctx.lineTo(6 * scale, -4 * scale);
        ctx.lineTo(0, 0);
        ctx.closePath();
        ctx.fill();
        ctx.restore();

        ctx.font      = `bold ${9 * scale}px -apple-system, sans-serif`;
        ctx.fillStyle = '#1e293b';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('N', cx + northVector.x * (r + 8 * scale), cy + northVector.y * (r + 8 * scale));
    }

    _drawTimestamp(ctx, W, H, pad, scale) {
        const now = new Date().toLocaleString('en');
        ctx.font      = `${11 * scale}px -apple-system, sans-serif`;
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.textAlign = 'right';
        ctx.fillText(`RSMarking Pro · ${now}`, W - pad, H - pad);
    }


    async _exportSVG(opts) {
        if (this._is3DExport()) {
            const canvas = await this._renderCesiumToCanvas(opts);
            const ns = 'http://www.w3.org/2000/svg';
            const svg = document.createElementNS(ns, 'svg');
            svg.setAttribute('xmlns', ns);
            svg.setAttribute('width', canvas.width);
            svg.setAttribute('height', canvas.height);
            svg.setAttribute('viewBox', `0 0 ${canvas.width} ${canvas.height}`);

            const image = document.createElementNS(ns, 'image');
            image.setAttribute('x', 0);
            image.setAttribute('y', 0);
            image.setAttribute('width', canvas.width);
            image.setAttribute('height', canvas.height);
            image.setAttribute('href', canvas.toDataURL('image/png'));
            svg.appendChild(image);

            const svgStr = '<?xml version="1.0" encoding="UTF-8"?>\n' +
                new XMLSerializer().serializeToString(svg);
            const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
            this._triggerDownload(URL.createObjectURL(blob), `${opts.filename}.svg`);
            return;
        }

        const map   = this._getMap();
        const mapEl = map?.getContainer();
        if (!mapEl) throw new Error('Map instance is not initialized');

        const W   = mapEl.clientWidth;
        const H   = mapEl.clientHeight;
        const ns  = 'http://www.w3.org/2000/svg';
        const svg = document.createElementNS(ns, 'svg');

        svg.setAttribute('xmlns',   ns);
        svg.setAttribute('width',   W);
        svg.setAttribute('height',  H);
        svg.setAttribute('viewBox', `0 0 ${W} ${H}`);

        const bg = document.createElementNS(ns, 'rect');
        bg.setAttribute('width',  W);
        bg.setAttribute('height', H);
        bg.setAttribute('fill',   opts.includeBasemap ? '#e8f4f8' : '#f8fafc');
        svg.appendChild(bg);

        if (opts.includeBasemap) {
            const bc = await this._captureBasemap(mapEl);
            if (bc) {
                const imgEl = document.createElementNS(ns, 'image');
                imgEl.setAttribute('x',      0);
                imgEl.setAttribute('y',      0);
                imgEl.setAttribute('width',  W);
                imgEl.setAttribute('height', H);
                imgEl.setAttribute('href',   bc.toDataURL('image/png'));
                svg.appendChild(imgEl);
            }
        }

        if (opts.includeVectors) {
            const leafletSvg = mapEl.querySelector('.leaflet-overlay-pane svg');
            if (leafletSvg) {
                const g = document.createElementNS(ns, 'g');
                g.setAttribute('id', 'vector-layers');
                Array.from(leafletSvg.children).forEach(child =>
                    g.appendChild(child.cloneNode(true))
                );
                svg.appendChild(g);
            }
        }

        const svgStr = '<?xml version="1.0" encoding="UTF-8"?>\n' +
            new XMLSerializer().serializeToString(svg);
        const blob = new Blob([svgStr], { type: 'image/svg+xml;charset=utf-8' });
        this._triggerDownload(URL.createObjectURL(blob), `${opts.filename}.svg`);
    }


    _downloadCanvas(canvas, opts) {
        const mime = opts.format === 'jpeg' ? 'image/jpeg' : 'image/png';
        const data = opts.format === 'jpeg'
            ? canvas.toDataURL(mime, opts.jpegQuality / 100)
            : canvas.toDataURL(mime);
        this._triggerDownload(data, `${opts.filename}.${opts.format}`);
    }

    _triggerDownload(href, filename) {
        const a    = document.createElement('a');
        a.href     = href;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        if (href.startsWith('blob:')) {
            setTimeout(() => URL.revokeObjectURL(href), 5000);
        }
    }


    async _exportGISFile(opts) {
        const payload = this._buildGISExportPayload(opts);
        if (!payload.raster_ids.length && !payload.vector_layers.length) {
            throw new Error('Select at least one loaded raster or visible vector layer.');
        }

        const { blob, filename } = await RasterAPI.exportWorkspaceFile(payload);
        const url = URL.createObjectURL(blob);
        this._triggerDownload(url, filename || `${opts.filename}.zip`);
    }

    _buildGISExportPayload(opts) {
        return {
            filename: opts.filename || 'RSMarking_Export',
            raster_ids: opts.includeRasters ? this._getActiveRasterExportIds() : [],
            vector_layers: opts.includeVectors ? this._getVisibleVectorExportLayers() : [],
        };
    }

    _getActiveRasterExportIds() {
        const activeIds = new Set(Array.from(Store.state.activeLayerIds ?? [], String));
        const ids = Store.state.rasters
            .filter((raster) => (
                activeIds.has(String(raster.id)) ||
                activeIds.has(String(raster.index_id))
            ))
            .map((raster) => Number(raster.index_id ?? raster.id))
            .filter((id) => Number.isFinite(id));
        return Array.from(new Set(ids));
    }

    _getVisibleVectorExportLayers() {
        const visibleIds = new Set(Array.from(Store.state.visibleVectorLayerIds ?? [], String));
        return Store.state.vectorLayers
            .filter((layer) => visibleIds.has(String(layer.id)))
            .map((layer) => ({
                id: String(layer.id),
                name: layer.name || `Layer_${layer.id}`,
            }));
    }


    _bindUIEvents() {
        if (this._uiBound) return;
        this._uiBound = true;

        document.querySelectorAll('input[name="export-format"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this._syncFilenameExt();
                this._syncJpegQualityVisibility();
                this._syncExportModeUI();
            });
        });

        // EnglishLine style selectorEnglish
        const graticuleChk        = document.getElementById('export-include-graticule');
        const graticuleStyleGroup = document.getElementById('graticule-style-group');
        if (graticuleChk && graticuleStyleGroup) {
            graticuleChk.addEventListener('change', () => {
                graticuleStyleGroup.classList.toggle('hidden', !graticuleChk.checked);
            });
        }
    }

    _syncFilenameExt() {
        const fmt   = this._getSelectedFormat();
        const extEl = document.getElementById('export-filename-ext');
        if (extEl) extEl.textContent = fmt === 'file' ? '.zip' : `.${fmt}`;
    }

    _syncJpegQualityVisibility() {
        const fmt   = this._getSelectedFormat();
        const group = document.getElementById('jpeg-quality-group');
        if (group) group.style.opacity = fmt === 'jpeg' ? '1' : '0.4';
    }

    _syncExportModeUI() {
        const isFile = this._getSelectedFormat() === 'file';
        document.querySelectorAll('[data-export-image-option]').forEach((el) => {
            el.classList.toggle('opacity-40', isFile);
            el.classList.toggle('pointer-events-none', isFile);
        });

        const imageSettings = document.getElementById('export-image-settings');
        if (imageSettings) {
            imageSettings.classList.toggle('opacity-40', isFile);
            imageSettings.querySelectorAll('input, select').forEach((input) => {
                input.disabled = isFile;
            });
        }

        const executeLabel = document.getElementById('export-execute-label');
        if (executeLabel) {
            executeLabel.textContent = isFile ? 'Export GIS File' : 'Export Image';
        }

        const refreshBtn = document.getElementById('export-preview-refresh-btn');
        refreshBtn?.classList.toggle('hidden', isFile);

        if (isFile) this.refreshPreview();
    }

    _getSelectedFormat() {
        return document.querySelector('input[name="export-format"]:checked')?.value ?? 'png';
    }

    _collectOptions() {
        return {
            format:              this._getSelectedFormat(),
            includeBasemap:      document.getElementById('export-include-basemap')?.checked      ?? true,
            includeVectors:      document.getElementById('export-include-vectors')?.checked      ?? true,
            includeRasters:      document.getElementById('export-include-rasters')?.checked      ?? true,
            includeDecorations:  document.getElementById('export-include-decorations')?.checked  ?? true,
            includeGraticule:    document.getElementById('export-include-graticule')?.checked    ?? false,
            includeFrameLabels:  document.getElementById('export-include-frame-labels')?.checked ?? false,
            graticuleStyle:      document.querySelector('input[name="graticule-style"]:checked')?.value ?? 'solid',
            scale:               parseInt(document.getElementById('export-dpi')?.value           ?? '2'),
            jpegQuality:         parseInt(document.getElementById('export-jpeg-quality')?.value  ?? '92'),
            filename:            document.getElementById('export-filename')?.value?.trim()
                             || 'RSMarking_Export',
        };
    }

    _niceNumber(n) {
        const p = Math.pow(10, Math.floor(Math.log10(n)));
        const f = n / p;
        if (f < 1.5) return p;
        if (f < 3.5) return 2 * p;
        if (f < 7.5) return 5 * p;
        return 10 * p;
    }

    _clamp(value, min, max) {
        if (!Number.isFinite(value)) return min;
        return Math.min(max, Math.max(min, value));
    }

    async _loadHtml2Canvas() {
        if (this._html2canvasLoaded || window.html2canvas) return;
        if (this._html2canvasPromise) return this._html2canvasPromise;
        this._html2canvasPromise = new Promise((resolve, reject) => {
            const s   = document.createElement('script');
            s.src     = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
            s.onload  = () => { this._html2canvasLoaded = true; resolve(); };
            s.onerror = reject;
            document.head.appendChild(s);
        }).finally(() => {
            this._html2canvasPromise = null;
        });
        await this._html2canvasPromise;
    }
}
