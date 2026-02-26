/**
 * AnnotationModule - 矢量标注模块
 * 负责手动几何绘制、交互逻辑及数据回传
 */
import { VectorAPI } from '../api/vector.js';
import { Store } from '../store/index.js';

export class AnnotationModule {
    constructor(app) {
        this.app = app;
        this.map = app.mapEngine.map;
        this.drawControl = null;
        this.currentHandler = null; // 当前激活的绘制处理器

        this.initEventListeners();
    }

    /**
     * 监听地图绘制事件
     */
    initEventListeners() {
        // 当用户完成一次绘制（多边形、矩形等）时触发
        this.map.on('draw:created', async (e) => {
            const { layerType, layer } = e;
            const geojson = layer.toGeoJSON();

            // 业务校验：必须先选中一个图层才能保存标注
            const activeLayerId = Store.state.activeVectorLayerId;
            if (!activeLayerId) {
                // 如果没有图层 ID，移除刚画好的临时层并提示
                this.map.removeLayer(layer);
                alert("请先在左侧选择或创建一个目标标注图层");
                return;
            }

            this.app.showGlobalLoader(true);
            try {
                // 1. 将几何数据发送到后端
                const newFeature = await VectorAPI.createFeature(
                    activeLayerId,
                    geojson.geometry,
                    {
                        category: "manual_annotation",
                        type: layerType,
                        created_at: new Date().toISOString()
                    }
                );

                console.log("[Annotation] 要素保存成功:", newFeature);

                // 2. 移除地图上的临时绘制层（关键：防止与即将刷新的正式数据重叠）
                this.map.removeLayer(layer);

                // 3. 通知 MapController 局部刷新当前视口的矢量数据
                if (this.app.mapController && this.app.mapController.refreshVectorLayer) {
                    await this.app.mapController.refreshVectorLayer(activeLayerId);
                }

                // 4. 停止当前绘制状态
                this.stopDrawing();

            } catch (err) {
                console.error("[Annotation] 保存失败:", err);
                alert("保存标注失败: " + err.message);
                this.map.removeLayer(layer); // 失败也清理临时层
            } finally {
                this.app.showGlobalLoader(false);
            }
        });
    }

    /**
     * 设置绘图模式
     * @param {string} mode - 'polygon', 'rectangle', 'marker'
     */
    startDrawing(mode) {
        // 先停止之前的绘制
        this.stopDrawing();

        // 检查 Leaflet.draw 插件是否存在
        if (typeof L.Draw === 'undefined') {
            console.error("[Annotation] 未找到 Leaflet.draw 插件，请确保已引入相关库文件");
            return;
        }

        const options = {
            shapeOptions: {
                color: '#4f46e5',
                fillOpacity: 0.2,
                weight: 3
            }
        };

        // 实例化 Leaflet.draw 的处理器
        switch (mode) {
            case 'polygon':
                this.currentHandler = new L.Draw.Polygon(this.map, options);
                break;
            case 'rectangle':
                this.currentHandler = new L.Draw.Rectangle(this.map, options);
                break;
            case 'marker':
                this.currentHandler = new L.Draw.Marker(this.map);
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
     * 停止绘制并清理 UI 状态
     */
    stopDrawing() {
        if (this.currentHandler) {
            this.currentHandler.disable();
            this.currentHandler = null;
        }
        this.updateUI(null);
    }

    /**
     * 更新工具栏按钮激活状态
     * 适配 HTML 中定义的按钮结构
     */
    updateUI(activeMode) {
        const buttons = document.querySelectorAll('.draw-btn');
        buttons.forEach(btn => {
            const onclickAttr = btn.getAttribute('onclick') || "";
            // 匹配字符串参数，例如 RS.setDrawMode('polygon')
            const isMatch = activeMode && onclickAttr.includes(`'${activeMode}'`);

            if (isMatch) {
                // 添加高亮样式（Tailwind 类名）
                btn.classList.add('ring-2', 'ring-indigo-600', 'bg-indigo-50', 'border-indigo-500');
            } else {
                // 移除高亮样式
                btn.classList.remove('ring-2', 'ring-indigo-600', 'bg-indigo-50', 'border-indigo-500');
            }
        });
    }

    /**
     * 切换编辑工具栏显隐
     * @param {boolean} enabled
     */
    toggleEditMode(enabled) {
        const toolbar = document.getElementById('drawing-toolbar');
        if (!toolbar) return;

        if (enabled) {
            toolbar.classList.remove('hidden');
        } else {
            toolbar.classList.add('hidden');
            this.stopDrawing();
        }
    }
}
