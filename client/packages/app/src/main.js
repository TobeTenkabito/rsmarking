import { MapEngine } from '../../core/src/map.js';
import { UIManager } from './core/UIManager.js';
import { GlobalBridge } from './core/GlobalBridge.js';
import { GlobalEvents } from './core/GlobalEvents.js';

import { MapController } from './modules/MapController.js';
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

/**
 * App Class - 纯粹的系统调度与依赖注入中心
 */
class App {
    constructor() {
        WelcomeModule.init();

        // 核心支持层
        this.ui = new UIManager(this);
        this.mapEngine = null;

        // 业务模块层
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
            // 1. 注入 HTML 骨架
            this.ui.injectModals();

            // 2. 初始化核心引擎
            this.mapEngine = new MapEngine('map');

            // 3. 实例化子模块
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

            // 4. 挂载全局方法与绑定事件
            new GlobalBridge(this).mount();
            new GlobalEvents(this).bindAll();

            // 5. 初始数据拉取
            await this.raster.refreshData();
            await this.project.refreshProjects();

            console.log("%c[RSMarking] 🟢 系统初始化成功", "color: #6366f1; font-weight: bold;");
        } catch (error) {
            console.error("[App] ❌ 初始化流程中断:", error);
        }
    }
}

// 实例化应用
const app = new App();
window.addEventListener('load', () => app.init());