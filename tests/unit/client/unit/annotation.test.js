import { describe, it, expect, vi } from 'vitest';
// 使用别名导入，确保路径解析一致
import { AnnotationModule } from '@app/modules/AnnotationModule.js';
import { TestLogger, createMockApp } from '@test-utils/test-helper.js';

describe('AnnotationModule 标注交互测试', () => {
    // 自动记录测试环境信息
    TestLogger.logEnvironment('annotation.test.js');

    it('undoLastPoint 应该在多边形模式下调用 deleteLastVertex', () => {
        // 使用工厂函数创建符合业务结构的 app (修复 mapEngine.map 报错)
        const mockApp = createMockApp();
        const module = new AnnotationModule(mockApp);

        const mockHandler = {
            enabled: () => true,
            deleteLastVertex: vi.fn()
        };
        module.currentHandler = mockHandler;

        module.undoLastPoint();
        expect(mockHandler.deleteLastVertex).toHaveBeenCalled();
    });

    it('resetCurrentAction 应该重置动作而不退出模式', () => {
        const mockApp = createMockApp();
        const module = new AnnotationModule(mockApp);

        const mockHandler = {
            enabled: () => true,
            disable: vi.fn(),
        };

        // 模拟内部方法以验证调用
        module.setDrawMode = vi.fn();
        module.currentHandler = mockHandler;
        module.currentType = 'polygon';

        module.resetCurrentAction();

        expect(mockHandler.disable).toHaveBeenCalled();
        expect(module.setDrawMode).toHaveBeenCalledWith('polygon');
    });
});