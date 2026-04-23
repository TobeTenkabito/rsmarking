/**
 * Modals.js - 聚合入口
 * 各 Modal 已拆分至 ./modals/ 子目录，此文件负责统一导出
 * 外部调用方无需感知内部结构变化
 */

import { indexModal }             from './modals/indexModal.js';
import { extractionModal }        from './modals/extractionModal.js';
import { mergeModal }             from './modals/mergeModal.js';
import { extractModal }           from './modals/extractModal.js';
import { calculatorModal }        from './modals/calculatorModal.js';
import { scriptModal }            from './modals/scriptModal.js';
import { detailPanel }            from './modals/detailPanel.js';
import { aiModal }                from './modals/aiModal.js';
import { attributeTablePanel }    from './modals/attributeTablePanel.js';
import { exportModal }            from './modals/exportModal.js';
import { clipModal }              from './modals/clipModal.js';
import { changeModal }            from './modals/changeModal.js';
import { conversionModal }        from './modals/conversionModal.js';

export const ModalTemplates = {
    indexModal,
    extractionModal,
    mergeModal,
    extractModal,
    calculatorModal,
    scriptModal,
    detailPanel,
    aiModal,
    attributeTablePanel,
    exportModal,
    clipModal,
    changeModal,
    conversionModal,
};
