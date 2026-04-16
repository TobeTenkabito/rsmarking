import { Store } from '../store/index.js';

export class GlobalBridge {
    constructor(app) {
        this.app = app;
    }

    mount() {
        window.RS = {
            // --- 基础操作 ---
            fetchRasters: () => this.app.raster.refreshData(),
            clearDatabase: async () => {
            await this.app.raster.handleClearDatabase();
            await this.app.project.handleDeleteAllProjects();},

            // --- 指数分析 ---
            openIndexModal: (type) => this.app.analysis?.openModal(type),
            closeIndexModal: () => this.app.analysis?.closeModal(),
            executeIndexCalculation: () => this.app.analysis?.execute(),
            showSpectrumMode:   (index_id)=>this.app.analysis?.toggleSpectrumMode(index_id),

            // --- 要素提取 ---
            openExtractionModal: (type) => this.app.extraction?.openModal(type),
            closeExtractionModal: () => this.app.extraction?.closeModal(),
            runExtraction: () => this.app.extraction?.run(),

            // --- 栅格计算器 ---
            openCalculatorModal: () => this.app.calculator?.openModal(),
            closeCalculatorModal: () => this.app.calculator?.closeModal(),
            updateCalculatorVariables: () => this.app.calculator?.handleExpressionChange(),
            executeCalculator: () => this.app.calculator?.execute(),
            insertCalcFunction: (fn) => this.app.calculator?.insertFunction(fn),
            toggleCalcHelp: () => this.app.calculator?.toggleHelp(),

            // --- 波段合成 ---
            openMergeModal: () => this.app.raster.handleOpenMergeModal(),
            closeMergeModal: () => document.getElementById('merge-modal')?.classList.add('hidden'),
            executeMerge: () => this.app.raster.handleExecuteMerge(),
            toggleMergeItem: (id) => this.app.raster.handleToggleMergeSelection(id),

            // --- 波段提取 ---
            openExtractModal: () => this.app.raster.handleOpenExtractModal(),
            closeExtractModal: () => document.getElementById('extract-modal')?.classList.add('hidden'),
            executeExtract: () => this.app.raster.handleExecuteExtract(),
            toggleExtractItem: (bandIndex) => this.app.raster.handleToggleExtractSelection(bandIndex),
            extractStepNext: () => this.app.raster.handleExtractStepNext(),
            extractStepBack: () => this.app.raster.handleExtractStepBack(),
            selectExtractSource: (rasterId) => this.app.raster.handleSelectExtractSource(rasterId),

            // --- UI 辅助 ---
            hideDetail: () => this.app.ui.hideDetail(),

            // --- 矢量项目系统 ---
            createProject: () => this.app.project.handleCreateProject(),
            selectProject: (id) => this.app.project.handleSelectProject(id),
            createLayer: () => this.app.project.handleCreateLayer(),
            toggleVectorLayer: (id) => this.app.project.handleToggleVectorLayer(id),

            // --- 标注工具控制 ---
            toggleEditMode: (enabled) => this.app.annotation?.toggleEditMode?.(enabled),
            toggleVectorVisibility: (layerId) => Store.toggleVectorVisibility(layerId),
            setActiveVectorLayer: (layerId) => Store.setActiveVectorLayer(layerId),
            setDrawMode: (mode) => this.app.project.handleSetDrawMode(mode),
            cancelDraw: () => this.app.project.handleCancelDraw(),
            exitEditMode: () => this.app.project.handleExitEditMode(),
            setDrawColor: (color) => Store.setDrawColor(color),
            deleteSelectedFeature: () => this.app.project.handleDeleteSelectedFeature(),
            deleteLayer: (layerId) => this.app.project.handleDeleteSelectedLayer(layerId),

            // 脚本编辑器
            openScriptEditor:       () => this.app.script?.openScriptEditor(),
            closeScriptEditor:      () => this.app.script?.closeScriptEditor(),
            executeScript:          () => this.app.script?.executeScript(),
            clearScriptEditor:      () => this.app.script?.clearEditor(),
            showScriptHistory:      () => this.app.script?.showHistory(),
            loadScriptFromHistory: (id) => this.app.script?.loadFromHistory(id),

            // --- AI 智能助手 ---
            openAIModal:        ()  => this.app.ai?.openModal(),
            closeAIModal:       ()  => this.app.ai?.closeModal(),
            aiExecute:          ()  => this.app.ai?.execute(),
            aiConfirmCreate:    ()  => this.app.ai?.confirmCreate(),
            aiConfirmOverwrite: ()  => this.app.ai?.confirmOverwrite(),

            // --- 属性表 ---
            openAttriVector     : (layerId, layerName)  => this.app.attributeTable?.open(layerId, layerName),
            attrClose           : ()                    => this.app.attributeTable?.close(),
            attrRefresh         : ()                    => this.app.attributeTable?.refresh(),
            attrToggleExpand    : ()                    => this.app.attributeTable?.toggleExpand(),
            attrAddColumn       : ()                    => this.app.attributeTable?.addColumn(),
            attrRenameColumn    : (fid, alias)          => this.app.attributeTable?.renameColumn(fid, alias),
            attrDeleteColumn    : (fid, name)           => this.app.attributeTable?.deleteColumn(fid, name),
            attrColumnMenu      : (e, fid, fname, sys)  => this.app.attributeTable?.showColumnMenu(e, fid, fname, sys),
            attrEditCell        : (td)                  => this.app.attributeTable?.editCell(td),
            attrDeleteFeature   : (featureId)           => this.app.attributeTable?.deleteFeature(featureId),
            attrrenameRasterField: (fieldId, alias)     => this.app.attributeTable?.renameRasterField(fieldId, alias),
            attrdeleteRasterField: (fieldId, fieldName) => this.app.attributeTable?.deleteRasterField(fieldId, fieldName),
            attreditRasterDefault: (td)                 => this.app.attributeTable?.editRasterDefault(td),

            openAttriRaster     : (rasterId, rasterName)=> {
                const rasters = Store.state?.rasters ?? [];
                const raster  = rasters.find(r => String(r.index_id) === String(rasterId));
                void this.app.attributeTable?.openRaster(rasterId, rasterName, raster ?? null);},

            // --- 导出 ---
            openExportModal:        ()=> this.app.export?.openModal(),
            closeExportModal:       ()=> this.app.export?.closeModal(),
            refreshExportPreview:   ()=> this.app.export?.refreshPreview(),
            executeExport:          ()=> this.app.export?.executeExport(),

            // --- 空间裁剪 ---
            openClipModal:  () => this.app.ui.openClipModal(),
            closeClipModal: () => this.app.ui.closeClipModal(),
            executeClip: () => {
                const type = document.querySelector('input[name="clip-type"]:checked')?.value;
                this.app.ui.closeClipModal();
                if (type === 'raster') {
                    this.app.clip?.startClipRasterByDraw();
                } else if (type === 'vector') {
                    const source  = document.querySelector('input[name="clip-source"]:checked')?.value;
                    const layerId = document.getElementById('clip-vector-layer-select')?.value || undefined;
                    if (source === 'bounds') {
                        this.app.clip?.clipVectorByActiveBounds(layerId);
                    } else {
                        this.app.clip?.startClipVectorByDraw(layerId);
                    }
                } else if (type === 'layer') {
                    const knifeId  = document.getElementById('clip-knife-layer-select')?.value || undefined;
                    const targetId = document.getElementById('clip-vector-layer-select')?.value || undefined;
                    if (!knifeId) {
                        this.app.ui.showToast('请选择裁剪刀图层', 'warning');
                        return;
                    }
                    this.app.clip?.clipVectorByLayer(knifeId, targetId);
                }
            },

            // --- 變化檢測 ---
            openChangeModal:        ()  => this.app.change?.open(),
            closeChangeModal:       ()  => this.app.change?.close(),
            runChangeDetection:     ()  => this.app.change?.run(),
            switchChangeMethod:     (m) => this.app.change?.switchMethod(m),
            loadChangeResult:       (w) => this.app.change?.loadResultToMap(w),

            // 矢量转栅格
            openConversionModal:  () => this.app.conversion?.openModal(),
            closeConversionModal: () => this.app.conversion?.closeModal(),
            handleConversionNameInput: () => this.app.conversion?.handleNameInput(),
            handleConversionStepBack:  () => this.app.conversion?.handleStepBack(),
            handleConversionStepNext:  () => this.app.conversion?.handleStepNext(),
            handleConversionExecute:   () => this.app.conversion?.handleExecute(),
            handleConversionSelectLayer: (id) => this.app.conversion?.handleSelectLayer(id),
            handleConversionSelectRef:   (id) => this.app.conversion?.handleSelectRef(id),


            // 兼容性接口
            refreshData: () => this.app.raster.refreshData(),
            toggleGlobeView: () => this.app.mapEngine?.toggleGlobeView(),
        };
    }
}