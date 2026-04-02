import { RasterAPI } from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { Store } from '../store/index.js';

/**
 * AnalysisModule - 负责光谱指数计算逻辑
 */
export class AnalysisModule {
    constructor(app) {
        this.app = app;
        this.currentType = null;
    }
    /**
     * 打开计算弹窗并动态生成波段选择器
     */
    openModal(type) {
        if (Store.state.rasters.length === 0) {
            alert("工作站暂无影像，请先上传数据");
            return;
        }
        this.currentType = type;
        const content = document.getElementById('index-content');
        const bar = document.getElementById('index-modal-bar');
        content.innerHTML = ModalComponent.renderIndexConfig(type, Store.state.rasters);
        const themeColors = {
            'NDVI': '#10b981', // emerald
            'NDWI': '#3b82f6', // blue
            'NDBI': '#f59e0b', // amber
            'MNDWI': '#06b6d4' // cyan
        };

        if (bar) bar.style.backgroundColor = themeColors[type] || '#6366f1';
        document.getElementById('index-modal').classList.remove('hidden');
    }
    closeModal() {
        document.getElementById('index-modal').classList.add('hidden');
    }
    async execute() {
        const b1 = document.getElementById('index-b1-select').value;
        const b2 = document.getElementById('index-b2-select').value;
        const name = document.getElementById('index-name-input').value;
        if (!name) return alert("请输入结果图层名称");
        this.app.ui.showGlobalLoader(true);
        try {
            let result;
            switch (this.currentType) {
                case 'NDVI': result = await RasterAPI.calculateNDVI(b1, b2, name); break;
                case 'NDWI': result = await RasterAPI.calculateNDWI(b1, b2, name); break;
                case 'NDBI': result = await RasterAPI.calculateNDBI(b1, b2, name); break;
                case 'MNDWI': result = await RasterAPI.calculateMNDWI(b1, b2, name); break;
            }
            this.closeModal();
            await this.app.raster.refreshData();
        } catch (e) {
            alert(`空间运算失败: ${e.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    /**
    * 切換光譜拾取模式
    * @param {string|number} rasterId - 影像 index_id
    */
    toggleSpectrumMode(rasterId) {
    const isActive = Store.state.spectrumMode &&
                     Store.state.spectrumRasterId == rasterId;

    if (isActive) {
        // 再次點擊同一影像 → 退出模式
        Store.setSpectrumMode(false);
        this._closeSpectrumPanel();
        document.getElementById('map').style.cursor = '';
    } else {
        // 進入模式：綁定到指定影像
        Store.setSpectrumMode(true, rasterId);
        document.getElementById('map').style.cursor = 'crosshair';
        this._showSpectrumPanel(null); // 顯示空面板，等待點擊
    }
}

    /**
    * 執行光譜查詢（由 GlobalEvents 地圖點擊觸發）
    * @param {number} lng
    * @param {number} lat
    */
    async querySpectrumAt(lng, lat) {
    const rasterId = Store.state.spectrumRasterId;
    if (!rasterId) return;

    try {
        const result = await RasterAPI.querySpectrum(rasterId, lng, lat);
        if (!result) throw new Error("查詢返回空結果");
        Store.setSpectrumResult(result);
        this._showSpectrumPanel(result);
    } catch (e) {
        console.error("[AnalysisModule] 光譜查詢失敗:", e);
        this._showSpectrumPanel(null, e.message);
    }
}

    /**
    * 渲染光譜面板（純 DOM 操作，不依賴 Modal）
    */
    _showSpectrumPanel(result, errorMsg = null) {
    let panel = document.getElementById('spectrum-panel');

    // 首次創建面板
    if (!panel) {
        panel = document.createElement('div');
        panel.id = 'spectrum-panel';
        panel.style.cssText = `
            position: absolute; bottom: 40px; right: 16px; z-index: 1000;
            width: 300px; background: #1e1e2e; border: 1px solid #3f3f5a;
            border-radius: 10px; padding: 14px 16px; color: #e2e8f0;
            font-size: 13px; box-shadow: 0 4px 24px rgba(0,0,0,0.5);
            pointer-events: auto;
        `;
        document.getElementById('map').parentElement.appendChild(panel);
    }

    // 錯誤狀態
    if (errorMsg) {
        panel.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
                <span style="font-weight:600;color:#f87171">⚠ 光譜查詢</span>
                <button onclick="document.getElementById('spectrum-panel').remove()"
                    style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:16px">✕</button>
            </div>
            <p style="color:#f87171;margin:0">${errorMsg}</p>`;
        return;
    }

    // 等待點擊狀態
    if (!result) {
        panel.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
                <span style="font-weight:600;color:#a78bfa">📈 光譜查詢</span>
                <button id="spectrum-close-btn"
                    style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:16px">✕</button>
            </div>
            <p style="color:#94a3b8;margin:0;text-align:center;padding:12px 0">
                點擊地圖上任意像素查看光譜
            </p>`;
        document.getElementById('spectrum-close-btn')?.addEventListener('click', () => {
            this._closeSpectrumPanel();
            Store.setSpectrumMode(false);
            document.getElementById('map').style.cursor = '';
        });
        return;
    }

    // 有結果狀態：渲染波段條形圖
    const { bands, coordinate } = result;
    const values = bands.map(b => b.value ?? 0);
    const maxVal = Math.max(...values, 1);

    const bars = bands.map(b => {
        const pct = ((b.value ?? 0) / maxVal * 100).toFixed(1);
        const displayVal = b.value === null ? 'NoData'
                         : Number.isInteger(b.value) ? b.value
                         : b.value.toFixed(4);
        return `
            <div style="margin-bottom:6px">
                <div style="display:flex;justify-content:space-between;margin-bottom:2px">
                    <span style="color:#cbd5e1;font-size:11px">${b.name}</span>
                    <span style="color:#a78bfa;font-size:11px;font-weight:600">${displayVal}</span>
                </div>
                <div style="background:#2d2d44;border-radius:3px;height:6px;overflow:hidden">
                    <div style="width:${pct}%;height:100%;
                                background:linear-gradient(90deg,#6366f1,#a78bfa);
                                border-radius:3px;transition:width 0.3s ease">
                    </div>
                </div>
            </div>`;
    }).join('');

    panel.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <span style="font-weight:600;color:#a78bfa">📈 光譜</span>
            <button id="spectrum-close-btn"
                style="background:none;border:none;color:#94a3b8;cursor:pointer;font-size:16px">✕</button>
        </div>
        <div style="color:#64748b;font-size:11px;margin-bottom:10px">
            📍 ${coordinate.lng.toFixed(6)}, ${coordinate.lat.toFixed(6)}
        </div>
        ${bars}`;

    document.getElementById('spectrum-close-btn')?.addEventListener('click', () => {
        this._closeSpectrumPanel();
        Store.setSpectrumMode(false);
        document.getElementById('map').style.cursor = '';
    });
}

    _closeSpectrumPanel() {
    document.getElementById('spectrum-panel')?.remove();
    Store.setSpectrumResult(null);
}

}