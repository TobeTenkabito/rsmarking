/**
 * AnnotationModule
 *
 * Manual vector drawing for both the Leaflet 2D map and the Cesium 3D globe.
 * Both paths emit the same GeoJSON geometry/properties payloads so the
 * backend, area auto-fill, refresh, and 2D/3D display pipeline stay shared.
 */
import { VectorAPI } from '../api/vector.js';
import { Store } from '../store/index.js';
import { AreaAutoFill } from '../utils/AreaAutoFill.js';
import { t } from '../i18n/index.js';

const EARTH_RADIUS_METERS = 6378137;
const MIN_CIRCLE_RADIUS_METERS = 1;
const POINT_EPSILON = 1e-10;

function toRad(deg) {
    return deg * Math.PI / 180;
}

function toDeg(rad) {
    return rad * 180 / Math.PI;
}

function clampLatitude(lat) {
    return Math.max(-90, Math.min(90, lat));
}

function normalizeLongitude(lng) {
    return ((((lng + 180) % 360) + 360) % 360) - 180;
}

function normalizePoint(point) {
    return {
        lng: normalizeLongitude(Number(point.lng)),
        lat: clampLatitude(Number(point.lat)),
    };
}

function samePoint(a, b) {
    if (!a || !b) return false;
    return (
        Math.abs(a.lng - b.lng) < POINT_EPSILON &&
        Math.abs(a.lat - b.lat) < POINT_EPSILON
    );
}

function sanitizePath(points) {
    const result = [];
    for (const point of points) {
        if (!point) continue;
        const normalized = normalizePoint(point);
        if (!Number.isFinite(normalized.lng) || !Number.isFinite(normalized.lat)) continue;
        if (!samePoint(result[result.length - 1], normalized)) {
            result.push(normalized);
        }
    }
    return result;
}

function toCoordinate(point) {
    return [point.lng, point.lat];
}

function closeRing(points) {
    const ring = sanitizePath(points);
    if (ring.length === 0) return ring;
    if (!samePoint(ring[0], ring[ring.length - 1])) {
        ring.push({ ...ring[0] });
    }
    return ring;
}

function buildRectangleRing(a, b) {
    if (!a || !b || samePoint(a, b)) return [];
    const west = Math.min(a.lng, b.lng);
    const east = Math.max(a.lng, b.lng);
    const south = Math.min(a.lat, b.lat);
    const north = Math.max(a.lat, b.lat);

    if (Math.abs(east - west) < POINT_EPSILON || Math.abs(north - south) < POINT_EPSILON) {
        return [];
    }

    return closeRing([
        { lng: west, lat: south },
        { lng: east, lat: south },
        { lng: east, lat: north },
        { lng: west, lat: north },
    ]);
}

function buildCircleRing(center, radiusMeters, sides = 72) {
    if (!center || !Number.isFinite(radiusMeters) || radiusMeters <= 0) return [];

    const lat1 = toRad(center.lat);
    const lng1 = toRad(center.lng);
    const angularDistance = radiusMeters / EARTH_RADIUS_METERS;
    const ring = [];

    for (let i = 0; i <= sides; i++) {
        const bearing = (i / sides) * Math.PI * 2;
        const sinLat1 = Math.sin(lat1);
        const cosLat1 = Math.cos(lat1);
        const sinDistance = Math.sin(angularDistance);
        const cosDistance = Math.cos(angularDistance);

        const lat2 = Math.asin(
            sinLat1 * cosDistance +
            cosLat1 * sinDistance * Math.cos(bearing)
        );
        const lng2 = lng1 + Math.atan2(
            Math.sin(bearing) * sinDistance * cosLat1,
            cosDistance - sinLat1 * Math.sin(lat2)
        );

        ring.push({
            lng: normalizeLongitude(toDeg(lng2)),
            lat: clampLatitude(toDeg(lat2)),
        });
    }

    return ring;
}

function ringToGeoJSON(ring) {
    return ring.map(toCoordinate);
}

export class AnnotationModule {
    constructor(app) {
        this.app = app;
        this.map = app.mapEngine.map;
        this.drawControl = null;
        this.currentHandler = null;
        this.currentType = null;
        this.cesiumDraw = null;
        this._drawButtons = null;

        this.initEventListeners();
    }

    initEventListeners() {
        if (!this.map) return;

        this.map.on('draw:created', async (e) => {
            const { layerType, layer } = e;
            const geojson = layer.toGeoJSON();
            const extraProps = {};

            if (layerType === 'circle' && typeof layer.getRadius === 'function') {
                extraProps.radius_meters = layer.getRadius();
            }

            const saved = await this._saveDrawnFeature(
                layerType,
                geojson.geometry,
                extraProps
            );

            this.map.removeLayer(layer);
            if (saved) this.stopDrawing();
        });

        const mapContainer = this.map.getContainer();
        L.DomEvent.on(mapContainer, 'contextmenu', (e) => {
            if (this._isCesiumDrawing()) return;
            if (this.currentHandler && this.currentHandler.enabled()) {
                L.DomEvent.preventDefault(e);
                L.DomEvent.stopPropagation(e);
                this.undoLastPoint();
            }
        });

        document.addEventListener('keydown', (e) => {
            if (this._isCesiumDrawing()) {
                this._handleCesiumKeydown(e);
                return;
            }

            if (!this.currentHandler || !this.currentHandler.enabled()) return;

            if (e.key === 'Backspace' || e.key === 'Delete') {
                this.undoLastPoint();
            }

            if (e.key === 'Escape') {
                e.preventDefault();
                this.resetCurrentAction();
            }
        });
    }

    startDrawing(mode) {
        this.stopDrawing();

        if (this._is3DMode()) {
            this._startCesiumDrawing(mode);
            return;
        }

        if (typeof L.Draw === 'undefined') {
            console.error("[Annotation] Leaflet.draw plugin was not found");
            return;
        }

        this.currentType = mode;
        const color = Store.state.drawColor;
        const shapeOptions = {
            shapeOptions: {
                color,
                fillColor: color,
                fillOpacity: 0.2,
                weight: 3,
            },
        };

        switch (mode) {
            case 'polygon':
                this.currentHandler = new L.Draw.Polygon(this.map, shapeOptions);
                break;
            case 'rectangle':
                this.currentHandler = new L.Draw.Rectangle(this.map, shapeOptions);
                break;
            case 'polyline':
                this.currentHandler = new L.Draw.Polyline(this.map, {
                    shapeOptions: { color, weight: 3 },
                });
                break;
            case 'marker':
                this.currentHandler = new L.Draw.Marker(this.map);
                break;
            case 'circle':
                this.currentHandler = new L.Draw.Circle(this.map, shapeOptions);
                break;
            case 'circlemarker':
                this.currentHandler = new L.Draw.CircleMarker(this.map, {
                    shapeOptions: {
                        color,
                        fillColor: color,
                        fillOpacity: 0.8,
                        weight: 2,
                    },
                });
                break;
            default:
                console.warn("[Annotation] Unsupported draw mode:", mode);
                return;
        }

        if (this.currentHandler) {
            this.currentHandler.enable();
            this.updateUI(mode);
        }
    }

    undoLastPoint() {
        if (this._isCesiumDrawing()) {
            this._undoCesiumVertex();
            return;
        }

        if (this.currentHandler && typeof this.currentHandler.deleteLastVertex === 'function') {
            this.currentHandler.deleteLastVertex();
        } else {
            this.resetCurrentAction();
        }
    }

    resetCurrentAction() {
        const type = this.currentType;

        if (this._isCesiumDrawing()) {
            this._stopCesiumDrawing();
            if (type) this.startDrawing(type);
            return;
        }

        if (!this.currentHandler) return;
        this.currentHandler.disable();
        if (type) this.startDrawing(type);
    }

    stopDrawing() {
        if (this.currentHandler) {
            this.currentHandler.disable();
            this.currentHandler = null;
        }

        this._stopCesiumDrawing();
        this.currentType = null;
        this.updateUI(null);
    }

    updateUI(activeMode) {
        const buttons = this._drawButtons?.length
            ? this._drawButtons
            : (this._drawButtons = Array.from(document.querySelectorAll('.draw-btn')));
        buttons.forEach(btn => {
            const onclickAttr = btn.getAttribute('onclick') || "";
            const isMatch = activeMode && onclickAttr.includes(`'${activeMode}'`);
            if (isMatch) {
                btn.classList.add('ring-2', 'ring-indigo-600', 'bg-indigo-50', 'border-indigo-500');
            } else {
                btn.classList.remove('ring-2', 'ring-indigo-600', 'bg-indigo-50', 'border-indigo-500');
            }
        });

        const label = document.getElementById('draw-active-label');
        if (!label) return;

        const labelMap = {
            polygon:      t('draw.tool.polygon'),
            rectangle:    t('draw.tool.rectangle'),
            circle:       t('draw.tool.circle'),
            polyline:     t('draw.tool.polyline'),
            marker:       t('draw.tool.marker'),
            circlemarker: t('draw.tool.circlemarker'),
        };

        if (activeMode && labelMap[activeMode]) {
            label.textContent = t('draw.active', { tool: labelMap[activeMode] });
            label.closest('#draw-active-indicator')?.classList.replace('text-slate-400', 'text-indigo-600');
        } else {
            label.textContent = t('draw.none');
            label.closest('#draw-active-indicator')?.classList.replace('text-indigo-600', 'text-slate-400');
        }
    }

    toggleEditMode(enabled) {
        const toolbar = document.getElementById('drawing-toolbar');
        const parentSection = document.getElementById('vector-layer-section');
        if (!toolbar) return;

        if (enabled) {
            toolbar.classList.remove('hidden');
            if (parentSection) parentSection.classList.remove('hidden');
        } else {
            toolbar.classList.add('hidden');
            if (parentSection) parentSection.classList.add('hidden');
            this.stopDrawing();
        }
    }

    async _saveDrawnFeature(layerType, geometry, extraProps = {}) {
        const activeLayerId = Store.state.activeVectorLayerId;

        if (!activeLayerId) {
            console.warn("[Annotation] No active vector layer; drawing was not saved");
            return false;
        }

        this.app.ui.showGlobalLoader(true);

        try {
            const newFeature = await VectorAPI.createFeature(
                activeLayerId,
                geometry,
                {
                    category: "manual_annotation",
                    draw_type: layerType,
                    source: "web_editor",
                    created_at: new Date().toISOString(),
                    color: Store.state.drawColor,
                    ...extraProps,
                }
            );

            await AreaAutoFill.run(
                activeLayerId,
                newFeature.id,
                geometry,
                {
                    draw_type: layerType,
                    ...extraProps,
                }
            );

            if (this.app.mapController?.refreshVectorLayer) {
                await this.app.mapController.refreshVectorLayer(activeLayerId);
            }

            return true;
        } catch (err) {
            console.error("[Annotation] Save failed:", err);
            return false;
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    _is3DMode() {
        const engine = this.app?.mapEngine;
        if (typeof engine?.is3DMode === 'function') return engine.is3DMode();
        return !!engine?._is3D;
    }

    _getCesiumViewer() {
        const engine = this.app?.mapEngine;
        if (typeof engine?.getCesiumViewer === 'function') return engine.getCesiumViewer();
        return engine?._cesiumViewer ?? null;
    }

    _isCesiumDrawing() {
        return !!this.cesiumDraw;
    }

    _startCesiumDrawing(mode) {
        if (typeof Cesium === 'undefined') {
            console.error("[Annotation] Cesium was not found");
            return;
        }

        const viewer = this._getCesiumViewer();
        if (!viewer) {
            console.error("[Annotation] Cesium viewer is not ready");
            return;
        }

        this.currentType = mode;
        const handler = new Cesium.ScreenSpaceEventHandler(viewer.canvas);

        this.cesiumDraw = {
            mode,
            viewer,
            handler,
            vertices: [],
            cursor: null,
            color: Store.state.drawColor,
            entities: {},
            saving: false,
            previousCursor: viewer.canvas.style.cursor,
            cameraControls: this._disableCesiumCamera(viewer),
        };

        viewer.canvas.style.cursor = 'crosshair';

        handler.setInputAction(
            movement => this._handleCesiumLeftClick(movement),
            Cesium.ScreenSpaceEventType.LEFT_CLICK
        );
        handler.setInputAction(
            movement => this._handleCesiumMouseMove(movement),
            Cesium.ScreenSpaceEventType.MOUSE_MOVE
        );
        handler.setInputAction(
            movement => this._handleCesiumDoubleClick(movement),
            Cesium.ScreenSpaceEventType.LEFT_DOUBLE_CLICK
        );
        handler.setInputAction(
            movement => this._handleCesiumRightClick(movement),
            Cesium.ScreenSpaceEventType.RIGHT_CLICK
        );

        this.updateUI(mode);
    }

    _stopCesiumDrawing() {
        const state = this.cesiumDraw;
        if (!state) return;

        if (state.handler && !state.handler.isDestroyed()) {
            state.handler.destroy();
        }

        for (const entity of Object.values(state.entities)) {
            if (entity) state.viewer.entities.remove(entity);
        }

        this._restoreCesiumCamera(state.viewer, state.cameraControls);
        state.viewer.canvas.style.cursor = state.previousCursor || '';
        state.viewer.scene.requestRender?.();
        this.cesiumDraw = null;
    }

    _disableCesiumCamera(viewer) {
        const controller = viewer.scene.screenSpaceCameraController;
        const previous = {
            enableRotate: controller.enableRotate,
            enableTranslate: controller.enableTranslate,
            enableZoom: controller.enableZoom,
            enableTilt: controller.enableTilt,
            enableLook: controller.enableLook,
        };

        controller.enableRotate = false;
        controller.enableTranslate = false;
        controller.enableZoom = false;
        controller.enableTilt = false;
        controller.enableLook = false;

        return previous;
    }

    _restoreCesiumCamera(viewer, previous) {
        if (!viewer || !previous) return;
        const controller = viewer.scene.screenSpaceCameraController;
        Object.assign(controller, previous);
    }

    _handleCesiumLeftClick(movement) {
        const state = this.cesiumDraw;
        if (!state || state.saving) return;

        const point = this._pickCesiumLngLat(movement.position);
        if (!point) return;

        if (state.mode === 'marker' || state.mode === 'circlemarker') {
            state.vertices = [point];
            this._syncCesiumPreviewEntities();
            void this._finishCesiumDrawing();
            return;
        }

        if (state.mode === 'rectangle' || state.mode === 'circle') {
            if (state.vertices.length === 0) {
                state.vertices.push(point);
                state.cursor = point;
                this._syncCesiumPreviewEntities();
                return;
            }

            state.cursor = point;
            void this._finishCesiumDrawing();
            return;
        }

        state.vertices.push(point);
        state.cursor = point;
        this._syncCesiumPreviewEntities();
    }

    _handleCesiumMouseMove(movement) {
        const state = this.cesiumDraw;
        if (!state || state.saving) return;

        const position = movement.endPosition || movement.position;
        const point = this._pickCesiumLngLat(position);
        if (!point) return;
        if (samePoint(state.cursor, point)) return;

        state.cursor = point;
        this._syncCesiumPreviewEntities();
    }

    _handleCesiumDoubleClick(movement) {
        const state = this.cesiumDraw;
        if (!state || state.saving) return;
        if (state.mode !== 'polygon' && state.mode !== 'polyline') return;

        const point = this._pickCesiumLngLat(movement.position);
        if (point && !samePoint(state.vertices[state.vertices.length - 1], point)) {
            state.vertices.push(point);
        }

        void this._finishCesiumDrawing();
    }

    _handleCesiumRightClick() {
        this._undoCesiumVertex();
    }

    _handleCesiumKeydown(e) {
        if (!this.cesiumDraw) return;

        if (e.key === 'Backspace' || e.key === 'Delete') {
            e.preventDefault();
            this._undoCesiumVertex();
        }

        if (e.key === 'Escape') {
            e.preventDefault();
            this.resetCurrentAction();
        }

        if (e.key === 'Enter') {
            e.preventDefault();
            void this._finishCesiumDrawing();
        }
    }

    _undoCesiumVertex() {
        const state = this.cesiumDraw;
        if (!state || state.saving) return;

        if (state.vertices.length > 0) {
            state.vertices.pop();
            state.cursor = state.vertices[state.vertices.length - 1] ?? state.cursor;
            this._syncCesiumPreviewEntities();
            return;
        }

        this.resetCurrentAction();
    }

    async _finishCesiumDrawing() {
        const state = this.cesiumDraw;
        if (!state || state.saving) return;

        const result = this._buildCesiumGeometry();
        if (!result) return;

        state.saving = true;
        const saved = await this._saveDrawnFeature(
            state.mode,
            result.geometry,
            result.extraProps
        );

        if (saved) {
            this.stopDrawing();
        } else if (this.cesiumDraw) {
            this.cesiumDraw.saving = false;
        }
    }

    _buildCesiumGeometry() {
        const state = this.cesiumDraw;
        if (!state) return null;

        const vertices = sanitizePath(state.vertices);

        switch (state.mode) {
            case 'marker':
            case 'circlemarker': {
                const point = vertices[0] ?? state.cursor;
                if (!point) return null;
                return {
                    geometry: {
                        type: 'Point',
                        coordinates: toCoordinate(point),
                    },
                    extraProps: {},
                };
            }

            case 'polyline': {
                if (vertices.length < 2) return null;
                return {
                    geometry: {
                        type: 'LineString',
                        coordinates: vertices.map(toCoordinate),
                    },
                    extraProps: {},
                };
            }

            case 'polygon': {
                const ring = closeRing(vertices);
                if (ring.length < 4) return null;
                return {
                    geometry: {
                        type: 'Polygon',
                        coordinates: [ringToGeoJSON(ring)],
                    },
                    extraProps: {},
                };
            }

            case 'rectangle': {
                const ring = buildRectangleRing(vertices[0], state.cursor);
                if (ring.length < 4) return null;
                return {
                    geometry: {
                        type: 'Polygon',
                        coordinates: [ringToGeoJSON(ring)],
                    },
                    extraProps: {},
                };
            }

            case 'circle': {
                const center = vertices[0];
                const edge = state.cursor;
                if (!center || !edge) return null;

                const radiusMeters = this._surfaceDistanceMeters(center, edge);
                if (radiusMeters < MIN_CIRCLE_RADIUS_METERS) return null;

                return {
                    geometry: {
                        type: 'Point',
                        coordinates: toCoordinate(center),
                    },
                    extraProps: {
                        radius_meters: radiusMeters,
                    },
                };
            }

            default:
                return null;
        }
    }

    _pickCesiumLngLat(position) {
        const viewer = this._getCesiumViewer();
        if (!viewer || !position || typeof Cesium === 'undefined') return null;

        let cartesian = null;

        if (viewer.scene.pickPositionSupported) {
            cartesian = viewer.scene.pickPosition(position);
        }

        if (!Cesium.defined(cartesian)) {
            const ray = viewer.camera.getPickRay(position);
            if (ray) cartesian = viewer.scene.globe.pick(ray, viewer.scene);
        }

        if (!Cesium.defined(cartesian)) return null;

        const cartographic = Cesium.Cartographic.fromCartesian(cartesian);
        const point = normalizePoint({
            lng: Cesium.Math.toDegrees(cartographic.longitude),
            lat: Cesium.Math.toDegrees(cartographic.latitude),
        });

        if (!Number.isFinite(point.lng) || !Number.isFinite(point.lat)) return null;
        return point;
    }

    _surfaceDistanceMeters(a, b) {
        if (!a || !b) return 0;
        if (typeof Cesium !== 'undefined') {
            const start = Cesium.Cartographic.fromDegrees(a.lng, a.lat);
            const end = Cesium.Cartographic.fromDegrees(b.lng, b.lat);
            return new Cesium.EllipsoidGeodesic(start, end).surfaceDistance;
        }

        const lat1 = toRad(a.lat);
        const lat2 = toRad(b.lat);
        const dLat = toRad(b.lat - a.lat);
        const dLng = toRad(b.lng - a.lng);
        const h = Math.sin(dLat / 2) ** 2 +
            Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2;

        return 2 * EARTH_RADIUS_METERS * Math.asin(Math.sqrt(h));
    }

    _syncCesiumPreviewEntities() {
        const state = this.cesiumDraw;
        if (!state || typeof Cesium === 'undefined') return;

        const lineCoords = this._getCesiumPreviewLineCoords();
        const polygonRing = this._getCesiumPreviewPolygonRing();
        const point = this._getCesiumPreviewPoint();

        if (lineCoords.length >= 2) {
            this._ensureCesiumLineEntity();
        } else {
            this._removeCesiumPreviewEntity('line');
        }

        if (polygonRing.length >= 4) {
            this._ensureCesiumPolygonEntity();
        } else {
            this._removeCesiumPreviewEntity('polygon');
        }

        if (point) {
            this._ensureCesiumPointEntity();
        } else {
            this._removeCesiumPreviewEntity('point');
        }

        state.viewer.scene.requestRender?.();
    }

    _getCesiumPreviewLineCoords() {
        const state = this.cesiumDraw;
        if (!state) return [];

        if (state.mode === 'circle') {
            const ring = this._getCesiumPreviewPolygonRing();
            return ring.length >= 4 ? ring : [];
        }

        if (state.mode === 'rectangle') {
            const ring = this._getCesiumPreviewPolygonRing();
            return ring.length >= 4 ? ring : [];
        }

        if (state.mode === 'polygon') {
            const path = sanitizePath([...state.vertices, state.cursor]);
            return path.length >= 3 ? closeRing(path) : path;
        }

        if (state.mode === 'polyline') {
            return sanitizePath([...state.vertices, state.cursor]);
        }

        return [];
    }

    _getCesiumPreviewPolygonRing() {
        const state = this.cesiumDraw;
        if (!state) return [];

        if (state.mode === 'rectangle') {
            return buildRectangleRing(state.vertices[0], state.cursor);
        }

        if (state.mode === 'circle') {
            const center = state.vertices[0];
            const edge = state.cursor;
            if (!center || !edge) return [];
            const radius = this._surfaceDistanceMeters(center, edge);
            return radius >= MIN_CIRCLE_RADIUS_METERS
                ? buildCircleRing(center, radius)
                : [];
        }

        if (state.mode === 'polygon') {
            const path = sanitizePath([...state.vertices, state.cursor]);
            return path.length >= 3 ? closeRing(path) : [];
        }

        return [];
    }

    _getCesiumPreviewPoint() {
        const state = this.cesiumDraw;
        if (!state) return null;
        if (state.mode === 'marker' || state.mode === 'circlemarker') {
            return state.vertices[0] ?? state.cursor;
        }
        return null;
    }

    _ensureCesiumLineEntity() {
        const state = this.cesiumDraw;
        if (!state || state.entities.line) return;

        const color = Cesium.Color.fromCssColorString(state.color);
        state.entities.line = state.viewer.entities.add({
            polyline: {
                positions: new Cesium.CallbackProperty(() => {
                    const coords = this._getCesiumPreviewLineCoords();
                    return this._coordsToCartesians(coords);
                }, false),
                width: 3,
                material: new Cesium.ColorMaterialProperty(color),
                clampToGround: true,
            },
        });
    }

    _ensureCesiumPolygonEntity() {
        const state = this.cesiumDraw;
        if (!state || state.entities.polygon) return;

        const color = Cesium.Color.fromCssColorString(state.color);
        state.entities.polygon = state.viewer.entities.add({
            polygon: {
                hierarchy: new Cesium.CallbackProperty(() => {
                    const ring = this._getCesiumPreviewPolygonRing();
                    const positions = this._coordsToCartesians(this._dropClosingPoint(ring));
                    return new Cesium.PolygonHierarchy(positions);
                }, false),
                material: color.withAlpha(0.25),
                outline: true,
                outlineColor: color,
                arcType: Cesium.ArcType.GEODESIC,
            },
        });
    }

    _ensureCesiumPointEntity() {
        const state = this.cesiumDraw;
        if (!state || state.entities.point) return;

        const color = Cesium.Color.fromCssColorString(state.color);
        state.entities.point = state.viewer.entities.add({
            position: new Cesium.CallbackProperty(() => {
                const point = this._getCesiumPreviewPoint();
                return point ? Cesium.Cartesian3.fromDegrees(point.lng, point.lat) : undefined;
            }, false),
            point: {
                color,
                pixelSize: state.mode === 'circlemarker' ? 10 : 8,
                outlineColor: Cesium.Color.WHITE,
                outlineWidth: 2,
                heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
                disableDepthTestDistance: Number.POSITIVE_INFINITY,
            },
        });
    }

    _removeCesiumPreviewEntity(key) {
        const state = this.cesiumDraw;
        if (!state?.entities[key]) return;
        state.viewer.entities.remove(state.entities[key]);
        delete state.entities[key];
    }

    _coordsToCartesians(coords) {
        if (!coords || coords.length === 0) return [];
        const flat = [];
        for (const coord of coords) {
            flat.push(coord.lng, coord.lat);
        }
        return Cesium.Cartesian3.fromDegreesArray(flat);
    }

    _dropClosingPoint(ring) {
        if (ring.length > 1 && samePoint(ring[0], ring[ring.length - 1])) {
            return ring.slice(0, -1);
        }
        return ring;
    }
}
