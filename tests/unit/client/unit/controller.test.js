import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MapController } from '@app/modules/MapController.js';
import { TestLogger, createMockApp } from '@test-utils/test-helper.js';

describe('MapController 业务编排测试', () => {
    TestLogger.logEnvironment('controller.test.js');

    let app;
    let controller;

    beforeEach(() => {
        // 使用初始状态注入功能
        app = createMockApp({
            initialState: {
                activeVectorLayerId: 'layer-init'
            }
        });
        controller = new MapController(app);
    });

    it('初始化时应正确绑定地图实例', () => {
        expect(controller.map).toBeDefined();
        // 验证 controller 内部引用的确实是 app 中的 map 实例
        expect(controller.map).toBe(app.mapEngine.map);
    });

    it('调用退出逻辑时应触发 Store 提交', () => {
        controller.exitWorkspace();

        // 验证是否通过 store.commit 修改了状态
        expect(app.store.commit).toHaveBeenCalled();
    });
});