import { RasterAPI } from '../api/raster.js';
import { ModalComponent } from '../../../ui/src/components/Modal.js';
import { Store } from '../store/index.js';

export class ExtractionModule {
    constructor(app) {
        this.app = app;
        this.currentType = null;
        this.selectedBandIds = []; // 存储用户依次选择的波段 ID
    }

    /**
     * 打开模态框并初始化第一个选择框
     */
    openModal(type) {
        if (Store.state.rasters.length === 0) {
            alert("请先准备源影像数据");
            return;
        }

        this.currentType = type;
        this.selectedBandIds = [];
        const content = document.getElementById('extraction-content');
        const bar = document.getElementById('extraction-modal-bar');

        // 初始化基础骨架
        content.innerHTML = ModalComponent.renderExtractionConfig(type, Store.state.rasters);

        // 绑定动态监听：当选择框变化时，决定是否开启下一个
        content.addEventListener('change', (e) => {
            if (e.target && e.target.classList.contains('band-selector')) {
                this.handleBandSelectionChange(e.target);
            }
        });

        const themeColors = {
            'VEGETATION': '#10b981',
            'WATER': '#3b82f6',
            'BUILDING': '#f59e0b',
            'CLOUD': '#64748b'
        };

        if (bar) bar.style.backgroundColor = themeColors[type] || '#f43f5e';
        document.getElementById('extraction-modal').classList.remove('hidden');
    }

    /**
     * 处理波段选择变化：动态开启下一个栏目
     */
    handleBandSelectionChange(target) {
        const container = document.getElementById('dynamic-bands-container');
        const allSelectors = Array.from(container.querySelectorAll('.band-selector'));
        const currentIndex = allSelectors.indexOf(target);

        // 如果当前选中的不是空值，且是最后一个选择框，则尝试开启下一个
        if (target.value && currentIndex === allSelectors.length - 1 && allSelectors.length < 5) {
            const nextIndex = allSelectors.length + 1;
            const newField = document.createElement('div');
            newField.className = 'mt-3 animate-fade-in';
            newField.innerHTML = `
                <label class="text-[10px] font-bold text-slate-400 uppercase mb-1.5 block">选择波段 ${nextIndex} (可选)</label>
                <select class="band-selector w-full p-3 bg-slate-50 border border-slate-200 rounded-xl text-xs outline-none focus:ring-2 focus:ring-blue-500/20">
                    <option value="">-- 请选择额外波段 --</option>
                    ${ModalComponent.renderSelectOptions(Store.state.rasters)}
                </select>
            `;
            container.appendChild(newField);
        }
    }

    closeModal() {
        document.getElementById('extraction-modal').classList.add('hidden');
    }

    /**
     * 执行任务：收集所有选中的波段 ID 作为参数传入
     */
    async run() {
        const container = document.getElementById('dynamic-bands-container');
        const selectors = Array.from(container.querySelectorAll('.band-selector'));

        // 过滤出用户真正选了值的 ID
        const bandIds = selectors.map(s => s.value).filter(val => val !== "");

        // 校验：最少需要填满两个
        if (bandIds.length < 2) {
            alert("该算法最少需要选择 2 个不同的波段数据");
            return;
        }

        const threshold = parseFloat(document.getElementById('extract-threshold-input')?.value || 0);
        const name = document.getElementById('extract-name-input')?.value || `Extract_${Date.now()}`;
        const mode = document.getElementById('extract-mode-input')?.value.trim() || "";

        this.app.showGlobalLoader(true);
        try {
            if (this.currentType === 'VEGETATION') {
                await RasterAPI.extractVegetation(bandIds, name, threshold , mode );
            } else if (this.currentType === 'WATER') {
                await RasterAPI.extractWater(bandIds, name, threshold, mode );
            } else if (this.currentType === 'BUILDING') {
                await RasterAPI.extractBuildings(bandIds, name, redId);
            } else if (this.currentType === 'CLOUD') {
                await RasterAPI.extractClouds(bandIds, name, swirId);
            }
            else {
                console.log("执行多波段提取:", bandIds);
                await RasterAPI.extractBuildings(bandIds, name, mode);
            }

            this.closeModal();
            await this.app.refreshData();
        } catch (e) {
            console.error(e);
            alert(`要素提取任务失败: ${e.message}`);
        } finally {
            this.app.showGlobalLoader(false);
        }
    }
}
