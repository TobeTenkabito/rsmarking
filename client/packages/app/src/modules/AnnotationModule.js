/**
 * AnnotationModule - 矢量标注模块
 * 负责手动几何绘制、交互逻辑及数据回传
 */
import { VectorAPI } from '../api/vector.js';
import { Store } from '../store/index.js';
import { AreaAutoFill } from '../glue/AreaAutoFill.js';

export class AnnotationModule {
    constructor(app) {
        this.app = app;
        this.map = app.mapEngine.map;
        this.drawControl = null;
        this.currentHandler = null; // 当前激活的绘制处理器
        this.currentType = null;    // 记录当前绘制类型

        this.initEventListeners();
    }
    /**
     * 监听地图绘制事件
     */
    initEventListeners() {
        if (!this.map) return;
        // 当用户完成一次绘制（多边形、矩形等）时触发
        this.map.on('draw:created', async (e) => {
            const { layerType, layer } = e;
            const geojson = layer.toGeoJSON();
            const activeLayerId = Store.state.activeVectorLayerId;

            if (!activeLayerId) {
                this.map.removeLayer(layer);
                console.warn("[Annotation] 未选择目标图层，放弃保存");
                return;
            }

            this.app.ui.showGlobalLoader(true);
            try {
                const extraProps = {};
                if (layerType === 'circle' && typeof layer.getRadius === 'function') {
                    extraProps.radius_meters = layer.getRadius();
            }

                const newFeature = await VectorAPI.createFeature(
                    activeLayerId,
                    geojson.geometry, {
                        category: "manual_annotation",
                        draw_type: layerType,
                        source: "web_editor",
                        created_at: new Date().toISOString(),
                        color: Store.state.drawColor,
                        ...extraProps
                    }
                );
                console.log("[Annotation] 要素保存成功:", newFeature);
                AreaAutoFill.run(activeLayerId, newFeature.id, geojson.geometry);

                this.map.removeLayer(layer);
                if (this.app.mapController && this.app.mapController.refreshVectorLayer) {
                    await this.app.mapController.refreshVectorLayer(activeLayerId);
                }
                this.stopDrawing();
            } catch (err) {
                console.error("[Annotation] 保存失败:", err);
                this.map.removeLayer(layer);
            } finally {
                this.app.ui.showGlobalLoader(false);
            }
        });
        const mapContainer = this.map.getContainer();
        L.DomEvent.on(mapContainer, 'contextmenu', (e) => {
            if (this.currentHandler && this.currentHandler.enabled()) {
                L.DomEvent.preventDefault(e);
                L.DomEvent.stopPropagation(e);
                console.log("[Annotation] 容器级右键拦截：退回上一个顶点");
                this.undoLastPoint();
            }
        });

        // 监听键盘事件
        document.addEventListener('keydown', (e) => {
            if (!this.currentHandler || !this.currentHandler.enabled()) return;
            // 撤销上一个点
            if (e.key === 'Backspace' || e.key === 'Delete') {
                this.undoLastPoint();
            }
            // 退出当前绘制
            if (e.key === 'Escape') {
                e.preventDefault();
                this.resetCurrentAction();
            }
        });
    }

    /**
     * 设置绘图模式
     * @param {string} mode - 'polygon', 'rectangle', 'marker'
     */
    startDrawing(mode) {
        this.stopDrawing();
        if (typeof L.Draw === 'undefined') {
            console.error("[Annotation] 未找到 Leaflet.draw 插件");
            return;
        }

        this.currentType = mode;
        const color = Store.state.drawColor;

        const shapeOptions = {
            shapeOptions: {
                color: color,
                fillColor: color,
                fillOpacity: 0.2,
                weight: 3
            }
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
                shapeOptions: { color, weight: 3 }
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
                        weight: 2
                    }
                });
                break;
            default:
                console.warn("[Annotation] 不支持的绘制模式:", mode);
                return;
        }

        if (this.currentHandler) {
            this.currentHandler.enable();
            this.updateUI(mode);
        }
    }

    /**
     * 【动作级】：退回上一个顶点（针对多边形/折线）
     */
    undoLastPoint() {
        if (this.currentHandler && typeof this.currentHandler.deleteLastVertex === 'function') {
            console.log("[Annotation] 退回上一个顶点");
            this.currentHandler.deleteLastVertex();
        } else {
            this.resetCurrentAction();
        }
    }

    /**
     * 【动作级】：重置当前动作（清空正在画的线条，但保留工具高亮）
     */
    resetCurrentAction() {
        if (!this.currentHandler) return;
        console.log("[Annotation] 重置当前动作");
        const type = this.currentType;
        this.currentHandler.disable();
        // 重新启动该模式以清空已画部分
        if (type) this.startDrawing(type);
    }

    /**
     * 停止绘制并清理状态
     */
    stopDrawing() {
        if (this.currentHandler) {
            this.currentHandler.disable();
            this.currentHandler = null;
        }
        this.currentType = null;
        this.updateUI(null);
    }

    /**
     * 更新工具栏按钮激活状态
     */
    updateUI(activeMode) {
    // 原有：更新 draw-btn 高亮
    const buttons = document.querySelectorAll('.draw-btn');
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
        polygon:      '多边形',
        rectangle:    '矩形',
        circle:       '圆形',
        polyline:     '线段',
        marker:       '标记点',
        circlemarker: '采样点',
    };

    if (activeMode && labelMap[activeMode]) {
        label.textContent = `绘制中：${labelMap[activeMode]}`;
        label.closest('#draw-active-indicator')?.classList.replace('text-slate-400', 'text-indigo-600');
    } else {
        label.textContent = '未选择工具';
        label.closest('#draw-active-indicator')?.classList.replace('text-indigo-600', 'text-slate-400');
    }
}

    /**
     * 切换编辑工具栏显隐
     */
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
}