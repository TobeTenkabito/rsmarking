/**
 * Modals.js - aggregation entry
 * Modals live under ./modals/ and are re-exported here
 * Callers do not need to know the internal structure
 */

import { indexModal }             from './modals/indexModal.js';
import { extractionModal }        from './modals/extractionModal.js';
import { mergeModal }             from './modals/mergeModal.js';
import { extractModal }           from './modals/extractModal.js';
import { resampleModal }          from './modals/resampleModal.js';
import { preprocessingModal }     from './modals/preprocessingModal.js';
import { demModal }               from './modals/demModal.js';
import { classificationModal }    from './modals/classificationModal.js';
import { calculatorModal }        from './modals/calculatorModal.js';
import { scriptModal }            from './modals/scriptModal.js';
import { detailPanel }            from './modals/detailPanel.js';
import { aiModal }                from './modals/aiModal.js';
import { attributeTablePanel }    from './modals/attributeTablePanel.js';
import { exportModal }            from './modals/exportModal.js';
import { clipModal }              from './modals/clipModal.js';
import { changeModal }            from './modals/changeModal.js';
import { conversionModal }        from './modals/conversionModal.js';
import { statisticsModal }        from './modals/statisticsModal.js';

export const ModalTemplates = {
    indexModal,
    extractionModal,
    mergeModal,
    extractModal,
    resampleModal,
    preprocessingModal,
    demModal,
    classificationModal,
    calculatorModal,
    scriptModal,
    detailPanel,
    aiModal,
    attributeTablePanel,
    exportModal,
    clipModal,
    changeModal,
    conversionModal,
    statisticsModal,
};
