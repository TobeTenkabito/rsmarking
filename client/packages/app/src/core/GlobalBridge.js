import { Store } from '../store/index.js';
import { t } from '../i18n/index.js';

export class GlobalBridge {
    constructor(app) {
        this.app = app;
    }

    mount() {
        window.RS = {
            // --- EnglishActions ---
            fetchRasters: () => this.app.raster.refreshData(),
            clearDatabase: async () => {
                if (!confirm(t('data.confirm.clearAll'))) return;
                this.app.ui.showGlobalLoader(true);
                try {
                    await Promise.all([
                        this.app.raster.handleClearDatabase({ confirmUser: false, reload: false }),
                        this.app.project.handleDeleteAllProjects({
                            confirmUser: false,
                            refresh: false,
                            showLoader: false,
                        }),
                    ]);
                    window.location.reload();
                } catch (err) {
                    console.error('[GlobalBridge] Failed to clear data:', err);
                    alert(t('data.alert.clearFailed', { message: err.message }));
                } finally {
                    this.app.ui.showGlobalLoader(false);
                }
            },

            // --- English ---
            openIndexModal: (type) => this.app.analysis?.openModal(type),
            closeIndexModal: () => this.app.analysis?.closeModal(),
            executeIndexCalculation: () => this.app.analysis?.execute(),
            showSpectrumMode:   (index_id)=>this.app.analysis?.toggleSpectrumMode(index_id),
            openRasterStatistics: (indexId) => this.app.rasterStatistics?.open(indexId),
            closeRasterStatistics: () => this.app.rasterStatistics?.close(),
            refreshRasterStatistics: () => this.app.rasterStatistics?.refresh(),
            selectRasterStatisticsBand: (bandIndex) => this.app.rasterStatistics?.selectBand(bandIndex),

            // --- Feature Extraction ---
            openExtractionModal: (type) => this.app.extraction?.openModal(type),
            closeExtractionModal: () => this.app.extraction?.closeModal(),
            runExtraction: () => this.app.extraction?.run(),

            // --- Raster Calculator ---
            openCalculatorModal: () => this.app.calculator?.openModal(),
            closeCalculatorModal: () => this.app.calculator?.closeModal(),
            updateCalculatorVariables: () => this.app.calculator?.handleExpressionChange(),
            executeCalculator: () => this.app.calculator?.execute(),
            insertCalcFunction: (fn) => this.app.calculator?.insertFunction(fn),
            toggleCalcHelp: () => this.app.calculator?.toggleHelp(),

            // --- Band Stacking ---
            openMergeModal: () => this.app.raster.handleOpenMergeModal(),
            closeMergeModal: () => document.getElementById('merge-modal')?.classList.add('hidden'),
            executeMerge: () => this.app.raster.handleExecuteMerge(),
            toggleMergeItem: (id) => this.app.raster.handleToggleMergeSelection(id),

            // --- Band Extraction ---
            openExtractModal: () => this.app.raster.handleOpenExtractModal(),
            closeExtractModal: () => document.getElementById('extract-modal')?.classList.add('hidden'),
            executeExtract: () => this.app.raster.handleExecuteExtract(),
            toggleExtractItem: (bandIndex) => this.app.raster.handleToggleExtractSelection(bandIndex),
            extractStepNext: () => this.app.raster.handleExtractStepNext(),
            extractStepBack: () => this.app.raster.handleExtractStepBack(),
            selectExtractSource: (rasterId) => this.app.raster.handleSelectExtractSource(rasterId),

            // --- Resampling ---
            openResampleModal: (rasterId) => this.app.resample?.openModal(rasterId),
            closeResampleModal: () => this.app.resample?.closeModal(),
            handleResampleInputChange: () => this.app.resample?.handleInputChange(),
            executeResample: () => this.app.resample?.execute(),

            // --- Radiometric and Geometric Preprocessing ---
            openPreprocessingModal: (mode, rasterId) => this.app.preprocessing?.openModal(mode, rasterId),
            closePreprocessingModal: () => this.app.preprocessing?.closeModal(),
            switchPreprocessingMode: (mode) => this.app.preprocessing?.switchMode(mode),
            handlePreprocessingInputChange: () => this.app.preprocessing?.handleInputChange(),
            executePreprocessing: () => this.app.preprocessing?.execute(),

            // --- Classification and Segmentation ---
            openClassificationModal: (mode, rasterId) => this.app.classification?.openModal(mode, rasterId),
            closeClassificationModal: () => this.app.classification?.closeModal(),
            switchClassificationMode: (mode) => this.app.classification?.switchMode(mode),
            handleClassificationInputChange: () => this.app.classification?.handleInputChange(),
            addClassificationSample: () => this.app.classification?.addSample(),
            removeClassificationSample: (index) => this.app.classification?.removeSample(index),
            executeClassification: () => this.app.classification?.execute(),

            // --- UI English ---
            hideDetail: () => this.app.ui.hideDetail(),
            positionRasterActionMenu: (details) => this.app.ui.positionRasterActionMenu(details),

            // --- VectorProjectSystem ---
            createProject: () => this.app.project.handleCreateProject(),
            selectProject: (id) => this.app.project.handleSelectProject(id),
            createLayer: () => this.app.project.handleCreateLayer(),
            toggleVectorLayer: (id) => this.app.project.handleToggleVectorLayer(id),

            // --- EnglishToolsEnglish ---
            toggleEditMode: (enabled) => this.app.annotation?.toggleEditMode?.(enabled),
            toggleVectorVisibility: (layerId) => Store.toggleVectorVisibility(layerId),
            setActiveVectorLayer: (layerId) => Store.setActiveVectorLayer(layerId),
            setDrawMode: (mode) => this.app.project.handleSetDrawMode(mode),
            cancelDraw: () => this.app.project.handleCancelDraw(),
            exitEditMode: () => this.app.project.handleExitEditMode(),
            setDrawColor: (color) => Store.setDrawColor(color),
            deleteSelectedFeature: () => this.app.project.handleDeleteSelectedFeature(),
            deleteLayer: (layerId) => this.app.project.handleDeleteSelectedLayer(layerId),

            // English
            openScriptEditor:       () => this.app.script?.openScriptEditor(),
            closeScriptEditor:      () => this.app.script?.closeScriptEditor(),
            executeScript:          () => this.app.script?.executeScript(),
            clearScriptEditor:      () => this.app.script?.clearEditor(),
            showScriptHistory:      () => this.app.script?.showHistory(),
            loadScriptFromHistory: (id) => this.app.script?.loadFromHistory(id),

            // --- AI English ---
            openAIModal:        ()  => this.app.ai?.openModal(),
            closeAIModal:       ()  => this.app.ai?.closeModal(),
            aiExecute:          ()  => this.app.ai?.execute(),
            aiConfirmCreate:    ()  => this.app.ai?.confirmCreate(),
            aiConfirmOverwrite: ()  => this.app.ai?.confirmOverwrite(),
            aiReloadFunctions:  ()  => this.app.ai?.reloadFunctions(),
            aiSelectFunction:   (name) => this.app.ai?.selectFunction(name),
            aiResetFunctionArgs: () => this.app.ai?.resetFunctionArgs(),
            aiRunSelectedFunction: () => this.app.ai?.runSelectedFunction(),
            aiStartNewAgentChat: () => this.app.ai?.startNewAgentChat(),
            aiArchiveConversation: () => this.app.ai?.archiveAgentConversation(),
            aiToggleArchivePanel: () => this.app.ai?.toggleArchivePanel(),
            aiLoadConversationArchive: (id) => this.app.ai?.loadConversationArchive(id),
            aiDeleteConversationArchive: (id) => this.app.ai?.deleteConversationArchive(id),
            aiClearConversationArchives: () => this.app.ai?.clearConversationArchives(),

            // --- Attribute table ---
            openAttriVector     : (layerId, layerName)  => this.app.attributeTable?.open(layerId, layerName),
            attrClose           : ()                    => this.app.attributeTable?.close(),
            attrRefresh         : ()                    => this.app.attributeTable?.refresh(),
            attrToggleExpand    : ()                    => this.app.attributeTable?.toggleExpand(),
            attrAddColumn       : ()                    => this.app.attributeTable?.addColumn(),
            attrExportCsv       : ()                    => this.app.attributeTable?.exportCsv(),
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

            // --- English ---
            openExportModal:        ()=> this.app.export?.openModal(),
            closeExportModal:       ()=> this.app.export?.closeModal(),
            refreshExportPreview:   ()=> this.app.export?.refreshPreview(),
            executeExport:          ()=> this.app.export?.executeExport(),

            // --- Spatial Clip ---
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
                        this.app.ui.showToast(t('clip.selectKnifeWarning'), 'warning');
                        return;
                    }
                    this.app.clip?.clipVectorByLayer(knifeId, targetId);
                }
            },

            // --- English ---
            openChangeModal:        ()  => this.app.change?.open(),
            closeChangeModal:       ()  => this.app.change?.close(),
            runChangeDetection:     ()  => this.app.change?.run(),
            switchChangeMethod:     (m) => this.app.change?.switchMethod(m),
            loadChangeResult:       (w) => this.app.change?.loadResultToMap(w),

            // Vector to Raster
            openConversionModal:  () => this.app.conversion?.openModal(),
            closeConversionModal: () => this.app.conversion?.closeModal(),
            handleConversionNameInput: () => this.app.conversion?.handleNameInput(),
            handleConversionStepBack:  () => this.app.conversion?.handleStepBack(),
            handleConversionStepNext:  () => this.app.conversion?.handleStepNext(),
            handleConversionExecute:   () => this.app.conversion?.handleExecute(),
            handleConversionSelectLayer: (id) => this.app.conversion?.handleSelectLayer(id),
            handleConversionSelectRef:   (id) => this.app.conversion?.handleSelectRef(id),
            openRasterToVectorModal: (id) => this.app.conversion?.openRasterToVectorModal(id),
            closeRasterToVectorModal: () => this.app.conversion?.closeRasterToVectorModal(),
            handleRasterVectorNameInput: () => this.app.conversion?.handleRasterVectorNameInput(),
            handleRasterVectorSelectRaster: (id) => this.app.conversion?.handleSelectRaster(id),
            handleRasterToVectorExecute: () => this.app.conversion?.handleRasterToVectorExecute(),


            // English
            refreshData: () => this.app.raster.refreshData(),
            toggleGlobeView: () => this.app.mapEngine?.toggleGlobeView(),
        };
    }
}
