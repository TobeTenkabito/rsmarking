import { describe, it, expect, vi } from 'vitest';
import { Store } from '@app/store/index.js';
import { TestLogger, createMockApp } from '@test-utils/test-helper.js';

describe('Store 核心状态流转测试', () => {
    TestLogger.logEnvironment('annotation.test.js');
    beforeEach(() => {
        // 重置状态
        Store.state.activeVectorLayerId = null;
        Store.state.visibleVectorLayerIds = new Set();
    });

    it('应该能正确切换图层的可见性', () => {
        const layerId = 'layer-123';
        Store.toggleVectorVisibility(layerId);
        expect(Store.state.visibleVectorLayerIds.has(layerId)).toBe(true);

        Store.toggleVectorVisibility(layerId);
        expect(Store.state.visibleVectorLayerIds.has(layerId)).toBe(false);
    });

    it('激活编辑模式时应自动将图层设为可见', () => {
        const layerId = 'layer-456';
        Store.setActiveVectorLayer(layerId);

        expect(Store.state.activeVectorLayerId).toBe(layerId);
        expect(Store.state.visibleVectorLayerIds.has(layerId)).toBe(true);
    });

    it('退出编辑模式时应清除 activeVectorLayerId 但保留可见性集合', () => {
        Store.setActiveVectorLayer('layer-1');
        Store.setActiveVectorLayer(null);

        expect(Store.state.activeVectorLayerId).toBe(null);
        expect(Store.state.visibleVectorLayerIds.has('layer-1')).toBe(true);
    });
});
