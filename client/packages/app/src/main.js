import { MapEngine } from '../../core/src/map.js';
import { UIManager } from './core/UIManager.js';
import { GlobalBridge } from './core/GlobalBridge.js';
import { GlobalEvents } from './core/GlobalEvents.js';

import { MapController } from './core/MapController.js';
import { AnalysisModule } from './modules/AnalysisModule.js';
import { ExtractionModule } from './modules/ExtractionModule.js';
import { AnnotationModule } from './modules/AnnotationModule.js';
import { RasterModule } from './modules/RasterModule.js';
import { ProjectModule } from './modules/ProjectModule.js';
import { CalculatorModule } from './modules/CalculatorModule.js';
import { ScriptModule } from './modules/ScriptModule.js';
import { AIModule } from './modules/AIModule.js';
import { WelcomeModule } from './modules/WelcomeModule.js';
import { AttributeTable } from './modules/AttributeTable.js';
import { ExportModule } from './modules/ExportModule.js';
import { ClipModule } from './modules/ClipModule.js';
import { ChangeDetectionModule } from './modules/ChangeDetectionModule.js';
import { ConversionModule } from './modules/ConversionModule.js';
import { RasterStatisticsModule } from './modules/RasterStatisticsModule.js';
import { ResampleModule } from './modules/ResampleModule.js';
import { ClassificationModule } from './modules/ClassificationModule.js';
import { PreprocessingModule } from './modules/PreprocessingModule.js';
import { DEMAnalysisModule } from './modules/DEMAnalysisModule.js';
import { RasterTransformModule } from './modules/RasterTransformModule.js';
import { initializeI18n, onLanguageChange } from './i18n/index.js';


class App {
    constructor() {
        WelcomeModule.init();

        this.ui = new UIManager(this);
        this.mapEngine = null;

        this.mapController = null;
        this.analysis = null;
        this.extraction = null;
        this.annotation = null;
        this.script = null;
        this.raster = null;
        this.project = null;
        this.ai = null;
        this.attributeTable = null;
        this.export = null;
        this.clip = null;
        this.change = null;
        this.conversion = null;
        this.rasterStatistics = null;
        this.resample = null;
        this.classification = null;
        this.preprocessing = null;
        this.demAnalysis = null;
        this.rasterTransform = null;
    }

    async init() {
        try {
            initializeI18n();
            this.ui.injectModals();

            this.mapEngine = new MapEngine('map');

            this.mapController = new MapController(this.mapEngine);
            this.analysis = new AnalysisModule(this);
            this.calculator = new CalculatorModule(this);
            this.extraction = new ExtractionModule(this);
            this.annotation = new AnnotationModule(this);
            this.script = new ScriptModule(this);
            this.raster = new RasterModule(this);
            this.project = new ProjectModule(this);
            this.ai = new AIModule(this);
            this.attributeTable = new AttributeTable(this);
            this.export = new ExportModule(this);
            this.clip = new ClipModule(this);
            this.change = new ChangeDetectionModule(this);
            this.conversion = new ConversionModule(this);
            this.rasterStatistics = new RasterStatisticsModule(this);
            this.resample = new ResampleModule(this);
            this.classification = new ClassificationModule(this);
            this.preprocessing = new PreprocessingModule(this);
            this.demAnalysis = new DEMAnalysisModule(this);
            this.rasterTransform = new RasterTransformModule(this);

            new GlobalBridge(this).mount();
            new GlobalEvents(this).bindAll();

            onLanguageChange(() => {
                this.ui.refreshLanguage();
                this.mapController?.updateUI();
                this.annotation?.updateUI(this.annotation.currentType);
            });

            await this.raster.refreshData();
            await this.project.refreshProjects();

            this.ui.refreshLanguage();

            console.log("%c[RSMarking] initialized", "color: #6366f1; font-weight: bold;");
        } catch (error) {
            console.error("[App] initialization failed", error);
        }
    }
}

const app = new App();
window.addEventListener('load', () => app.init());
