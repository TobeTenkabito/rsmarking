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
import { CalculatorModule } from "./modules/CalculatorModule.js" ;
import { ScriptModule } from './modules/ScriptModule.js';
import { AIModule } from "./modules/AIModule.js";
import { WelcomeModule } from './modules/WelcomeModule.js';
import { AttributeTable }   from './modules/AttributeTable.js';
import { ExportModule } from "./modules/ExportModule.js";
import { ClipModule } from "./modules/ClipModule.js";
import { ChangeDetectionModule } from './modules/ChangeDetectionModule.js';
import { ConversionModule } from "./modules/ConversionModule.js";


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
    }

    async init() {
        try {
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

            new GlobalBridge(this).mount();
            new GlobalEvents(this).bindAll();

            await this.raster.refreshData();
            await this.project.refreshProjects();

            console.log("%c[RSMarking] 🟢 系统初始化成功", "color: #6366f1; font-weight: bold;");
        } catch (error) {
            console.error("[App] ❌ 初始化流程中断:", error);
        }
    }
}

const app = new App();
window.addEventListener('load', () => app.init());