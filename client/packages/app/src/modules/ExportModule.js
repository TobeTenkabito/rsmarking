export class ExportModule {
    constructor(app) {
        this.app = app;
        this._html2canvasLoaded = false;
        this._uiBound = false;
    }

    _getMap() {
        const engine = this.app?.mapEngine;
        return engine?.map ?? engine;
    }

    openModal() {
        const modal = document.getElementById('export-modal');
        if (!modal) return;
        modal.classList.remove('hidden');
        this._bindUIEvents();
        this._syncFilenameExt();
        this._syncJpegQualityVisibility();
    }

    closeModal() {
        document.getElementById('export-modal')?.classList.add('hidden');
    }

    async refreshPreview() {
        const placeholder = document.getElementById('export-preview-placeholder');
        const canvas      = document.getElementById('export-preview-canvas');
        const loader      = document.getElementById('export-preview-loader');
        if (!canvas) return;

        loader?.classList.remove('hidden');
        placeholder?.classList.add('hidden');
        canvas.classList.add('hidden');

        try {
            const opts       = this._collectOptions();
            const fullCanvas = await this._renderToCanvas(opts);
            const container  = document.getElementById('export-preview-container');
            const ctx        = canvas.getContext('2d');

            canvas.width  = container.clientWidth  * window.devicePixelRatio;
            canvas.height = container.clientHeight * window.devicePixelRatio;
            canvas.style.width  = container.clientWidth  + 'px';
            canvas.style.height = container.clientHeight + 'px';
            ctx.drawImage(fullCanvas, 0, 0, canvas.width, canvas.height);
            canvas.classList.remove('hidden');
        } catch (e) {
            console.error('[ExportModule] Preview failed:', e);
            if (placeholder) {
                placeholder.classList.remove('hidden');
                placeholder.innerHTML =
                    `<p class="text-[10px] text-red-400">预览失败: ${e.message}</p>`;
            }
        } finally {
            loader?.classList.add('hidden');
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
            if (opts.format === 'svg') {
                await this._exportSVG(opts);
            } else {
                const canvas = await this._renderToCanvas(opts);
                this._downloadCanvas(canvas, opts);
            }
        } catch (e) {
            console.error('[ExportModule] Export failed:', e);
            alert(`导出失败：${e.message}`);
        } finally {
            btn.disabled = false;
            spinner?.classList.add('hidden');
        }
    }

    // ─────────────────────────────────────────────
    //  核心渲染管线
    // ─────────────────────────────────────────────

    async _renderToCanvas(opts) {
        const map   = this._getMap();
        const mapEl = map?.getContainer();
        if (!mapEl) throw new Error('地图实例未初始化');

        const W = mapEl.clientWidth  * opts.scale;
        const H = mapEl.clientHeight * opts.scale;

        // 经纬网需要在地图外侧留白（用于标注经纬度）
        const MARGIN = opts.includeGraticule ? Math.round(36 * opts.scale) : 0;

        const output = document.createElement('canvas');
        output.width  = W + MARGIN * 2;   // 左右各留 MARGIN
        output.height = H + MARGIN * 2;   // 上下各留 MARGIN
        const ctx = output.getContext('2d');

        // 外框背景（留白区域）
        ctx.fillStyle = '#ffffff';
        ctx.fillRect(0, 0, output.width, output.height);

        // ① 底图（绘制在偏移后的地图区域）
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

        // ② 栅格影像图层
        if (opts.includeRasters) {
            this._drawRasterLayers(ctx, mapEl, W, H);
        }

        // ③ 矢量标注图层
        if (opts.includeVectors) {
            await this._drawVectorLayers(ctx, mapEl, W, H);
        }

        // ④ 经纬网（绘制在地图区域内，线条部分）
        if (opts.includeGraticule) {
            this._drawGraticuleLines(ctx, map, W, H, opts.scale, opts.graticuleStyle);
        }

        // ⑤ 装饰元素
        if (opts.includeDecorations) {
            this._drawDecorations(ctx, W, H, opts.scale);
        }

        ctx.restore();

        // ⑥ 经纬度外框标注（在 translate 外绘制，使用绝对坐标）
        if (opts.includeGraticule) {
            this._drawGraticuleFrame(ctx, map, W, H, MARGIN, opts.scale);
        }

        return output;
    }

    // ─────────────────────────────────────────────
    //  经纬网：网格线
    // ─────────────────────────────────────────────

    /**
     * 计算合适的经纬网间隔（度）
     */
    _niceLatLngInterval(map) {
        const bounds = map.getBounds();
        const spanLng = bounds.getEast()  - bounds.getWest();
        const spanLat = bounds.getNorth() - bounds.getSouth();
        const span = Math.max(spanLng, spanLat);

        // 目标：屏幕上出现 4~6 条线
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
     * 将经纬度转换为地图容器内的像素坐标（已乘 scale）
     */
    _latlngToPixel(map, lat, lng, mapEl, scale) {
        const point = map.latLngToContainerPoint([lat, lng]);
        return { x: point.x * scale, y: point.y * scale };
    }

    _drawGraticuleLines(ctx, map, W, H, scale, style) {
    const interval = this._niceLatLngInterval(map);
    const bounds   = map.getBounds();

    // ✅ 往外各扩一个 interval，保证边缘线一定能画到
    // ✅ 用 floor/ceil 反过来：west 向下取整，east 向上取整
    const lngStart = Math.floor(bounds.getWest()  / interval) * interval;
    const lngEnd   = Math.ceil( bounds.getEast()  / interval) * interval;
    const latStart = Math.floor(bounds.getSouth() / interval) * interval;
    const latEnd   = Math.ceil( bounds.getNorth() / interval) * interval;

    ctx.save();
    ctx.strokeStyle = 'rgba(80, 100, 160, 0.55)';
    ctx.lineWidth   = Math.max(0.6, 0.8 * scale);
    ctx.setLineDash(style === 'dashed' ? [6 * scale, 5 * scale] : []);

    // ── 经线（垂直）：用中心纬度换算 x，y 从 0 画到 H ──
    for (let lng = lngStart; lng <= lngEnd + 1e-9; lng += interval) {
        const pt = map.latLngToContainerPoint([map.getCenter().lat, lng]);
        const x  = pt.x * scale;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, H);
        ctx.stroke();
    }

    // ── 纬线（水平）：用中心经度换算 y，x 从 0 画到 W ──
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

    // ─────────────────────────────────────────────
    //  经纬网：外框 + 经纬度标注
    // ─────────────────────────────────────────────

    _drawGraticuleFrame(ctx, map, W, H, MARGIN, scale) {
    const interval = this._niceLatLngInterval(map);
    const bounds   = map.getBounds();

    // ✅ 与 _drawGraticuleLines 保持一致
    const lngStart = Math.floor(bounds.getWest()  / interval) * interval;
    const lngEnd   = Math.ceil( bounds.getEast()  / interval) * interval;
    const latStart = Math.floor(bounds.getSouth() / interval) * interval;
    const latEnd   = Math.ceil( bounds.getNorth() / interval) * interval;

    const fontSize = Math.max(9, 9 * scale);
    const tickLen  = 5 * scale;

    ctx.save();

    // ── 外框矩形 ──
    ctx.strokeStyle = '#334155';
    ctx.lineWidth   = Math.max(1, 1.2 * scale);
    ctx.setLineDash([]);
    ctx.strokeRect(MARGIN, MARGIN, W, H);

    ctx.font      = `${fontSize}px -apple-system, "PingFang SC", sans-serif`;
    ctx.fillStyle = '#1e293b';

    // ── 经度标注（上下边框）──
    ctx.textAlign = 'center';
    for (let lng = lngStart; lng <= lngEnd + 1e-9; lng += interval) {
        const pt = map.latLngToContainerPoint([map.getCenter().lat, lng]);
        const px = pt.x * scale + MARGIN;

        // 只标注在可视范围内的
        if (px < MARGIN || px > MARGIN + W) continue;

        const label = this._formatDeg(lng, 'lng');

        // 上边
        ctx.beginPath();
        ctx.moveTo(px, MARGIN);
        ctx.lineTo(px, MARGIN - tickLen);
        ctx.stroke();
        ctx.textBaseline = 'bottom';
        ctx.fillText(label, px, MARGIN - tickLen - 2 * scale);

        // 下边
        ctx.beginPath();
        ctx.moveTo(px, MARGIN + H);
        ctx.lineTo(px, MARGIN + H + tickLen);
        ctx.stroke();
        ctx.textBaseline = 'top';
        ctx.fillText(label, px, MARGIN + H + tickLen + 2 * scale);
    }

    // ── 纬度标注（左右边框）──
    for (let lat = latStart; lat <= latEnd + 1e-9; lat += interval) {
        const pt = map.latLngToContainerPoint([lat, map.getCenter().lng]);
        const py = pt.y * scale + MARGIN;

        if (py < MARGIN || py > MARGIN + H) continue;

        const label = this._formatDeg(lat, 'lat');

        // 左边
        ctx.textAlign    = 'right';
        ctx.textBaseline = 'middle';
        ctx.beginPath();
        ctx.moveTo(MARGIN, py);
        ctx.lineTo(MARGIN - tickLen, py);
        ctx.stroke();
        ctx.fillText(label, MARGIN - tickLen - 3 * scale, py);

        // 右边
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
     * 格式化经纬度为 "120°E" / "30°N" 样式
     */
    _formatDeg(val, type) {
        const abs = Math.abs(val);
        const deg = Math.floor(abs);
        const min = Math.round((abs - deg) * 60);
        let str = min > 0 ? `${deg}°${String(min).padStart(2,'0')}′` : `${deg}°`;
        if (type === 'lng') str += val >= 0 ? 'E' : 'W';
        else                str += val >= 0 ? 'N' : 'S';
        return str;
    }

    // ─────────────────────────────────────────────
    //  底图捕获
    // ─────────────────────────────────────────────

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
            } catch { /* 跨域瓦片跳过 */ }
        });

        return out;
    }

    // ─────────────────────────────────────────────
    //  图层绘制
    // ─────────────────────────────────────────────

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

    // ─────────────────────────────────────────────
    //  装饰元素
    // ─────────────────────────────────────────────

    _drawDecorations(ctx, W, H, scale) {
        const pad = 16 * scale;
        ctx.save();
        this._drawScaleBar(ctx, W, H, pad, scale);
        this._drawNorthArrow(ctx, W, pad, scale);
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

    _drawNorthArrow(ctx, W, pad, scale) {
        const cx = W - pad - 18 * scale;
        const cy = pad + 30 * scale;
        const r  = 14 * scale;

        ctx.fillStyle = 'rgba(255,255,255,0.9)';
        ctx.beginPath();
        ctx.arc(cx, cy, r + 4 * scale, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = '#1e293b';
        ctx.beginPath();
        ctx.moveTo(cx, cy - r);
        ctx.lineTo(cx - 6 * scale, cy + 4 * scale);
        ctx.lineTo(cx, cy);
        ctx.closePath();
        ctx.fill();

        ctx.fillStyle = '#cbd5e1';
        ctx.beginPath();
        ctx.moveTo(cx, cy + r);
        ctx.lineTo(cx + 6 * scale, cy - 4 * scale);
        ctx.lineTo(cx, cy);
        ctx.closePath();
        ctx.fill();

        ctx.font      = `bold ${9 * scale}px -apple-system, sans-serif`;
        ctx.fillStyle = '#1e293b';
        ctx.textAlign = 'center';
        ctx.fillText('N', cx, cy - r - 4 * scale);
    }

    _drawTimestamp(ctx, W, H, pad, scale) {
        const now = new Date().toLocaleString('zh-CN');
        ctx.font      = `${11 * scale}px -apple-system, sans-serif`;
        ctx.fillStyle = 'rgba(0,0,0,0.35)';
        ctx.textAlign = 'right';
        ctx.fillText(`RSMarking Pro · ${now}`, W - pad, H - pad);
    }

    // ─────────────────────────────────────────────
    //  SVG 导出
    // ─────────────────────────────────────────────

    async _exportSVG(opts) {
        const map   = this._getMap();
        const mapEl = map?.getContainer();
        if (!mapEl) throw new Error('地图实例未初始化');

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

    // ─────────────────────────────────────────────
    //  下载
    // ─────────────────────────────────────────────

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
        setTimeout(() => URL.revokeObjectURL(href), 5000);
    }

    // ─────────────────────────────────────────────
    //  UI 绑定 & 工具
    // ─────────────────────────────────────────────

    _bindUIEvents() {
        if (this._uiBound) return;
        this._uiBound = true;

        document.querySelectorAll('input[name="export-format"]').forEach(radio => {
            radio.addEventListener('change', () => {
                this._syncFilenameExt();
                this._syncJpegQualityVisibility();
            });
        });

        // 经纬网复选框联动线型选择器
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
        if (extEl) extEl.textContent = `.${fmt}`;
    }

    _syncJpegQualityVisibility() {
        const fmt   = this._getSelectedFormat();
        const group = document.getElementById('jpeg-quality-group');
        if (group) group.style.opacity = fmt === 'jpeg' ? '1' : '0.4';
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

    async _loadHtml2Canvas() {
        if (this._html2canvasLoaded || window.html2canvas) return;
        await new Promise((resolve, reject) => {
            const s   = document.createElement('script');
            s.src     = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
            s.onload  = () => { this._html2canvasLoaded = true; resolve(); };
            s.onerror = reject;
            document.head.appendChild(s);
        });
    }
}
