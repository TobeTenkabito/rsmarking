import { Store } from '../store/index.js';
import { VectorAPI } from '../api/vector.js';

export class ProjectModule {
    constructor(app) {
        this.app = app;
    }

    async refreshProjects() {
        try {
            const projects = await VectorAPI.fetchProjects();
            Store.setProjects(projects);
        } catch (err) {
            console.error("[ProjectModule] 矢量项目加载失败:", err);
        }
    }

    async handleCreateProject() {
        const name = prompt("请输入新矢量项目名称：", "默认标注项目");
        if (!name) return;
        this.app.ui.showGlobalLoader(true);
        try {
            await VectorAPI.createProject(name);
            await this.refreshProjects();
        } catch (e) {
            alert(`创建项目失败: ${e.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    async handleSelectProject(projectId) {
        if (!projectId) {
            Store.setActiveProject(null);
            return;
        }
        const proj = Store.state.projects.find(p => p.id == projectId);
        if (!proj) return;

        Store.setActiveProject(proj);
        this.app.ui.showGlobalLoader(true);
        try {
            const layers = await VectorAPI.fetchLayers(proj.id);
            Store.setVectorLayers(layers);
        } catch (e) {
            console.error("[ProjectModule] 加载矢量图层失败:", e);
            alert(`加载矢量图层失败: ${e.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    async handleCreateLayer() {
        const activeProj = Store.state.activeProject;
        if (!activeProj) {
            alert("请先选择或创建一个矢量项目！");
            return;
        }
        const name = prompt("请输入新标注图层名称：", "建筑物标注");
        if (!name) return;

        const activeRasters = Array.from(Store.state.activeLayerIds);
        const sourceRasterId = activeRasters.length > 0 ? activeRasters[0] : null;

        this.app.ui.showGlobalLoader(true);
        try {
            await VectorAPI.createLayer(activeProj.id, name, sourceRasterId);
            await this.handleSelectProject(activeProj.id);
        } catch (e) {
            alert(`创建图层失败: ${e.message}`);
        } finally {
            this.app.ui.showGlobalLoader(false);
        }
    }

    handleToggleVectorLayer(layerId) {
        if (this.app.mapController && typeof this.app.mapController.toggleVectorLayer === 'function') {
            this.app.mapController.toggleVectorLayer(layerId);
        } else {
            console.warn("[ProjectModule] MapController.toggleVectorLayer 方法未找到");
        }
    }

    handleSetDrawMode(mode) {
        if (!Store.state.activeVectorLayerId) {
            alert("请先在左侧选择或创建一个目标标注图层");
            return;
        }
        if (this.app.annotation && typeof this.app.annotation.startDrawing === 'function') {
            this.app.annotation.startDrawing(mode);
        }
    }

    handleCancelDraw() {
        if (this.app.annotation) this.app.annotation.stopDrawing();
    }

    handleExitEditMode() {
        if (this.app.annotation) this.app.annotation.stopDrawing();
        Store.setActiveVectorLayer(null);
        if (this.app.mapController) {
            this.app.mapController.fetchViewportFeatures();
        }
    }

    async handleDeleteSelectedFeature() {
        const targetId = Store.state.selectedFeatureId;
        if (!targetId) return;

        if (confirm('确认删除该标注？')) {
            try {
                await VectorAPI.deleteFeature(targetId);
                Store.setSelectedFeatureId(null);
                const delBtn = document.getElementById('btn-delete-feature');
                if (delBtn) delBtn.classList.add('hidden');

                if (this.app.mapController) {
                    await this.app.mapController.refreshVectorLayer(Store.state.activeVectorLayerId);
                }
            } catch (err) {
                console.error('删除失败', err);
                alert('删除失败，请检查网络或控制台');
            }
        }
    }
}