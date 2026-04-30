/**
 * Modal.js
 * ModalComponent 对外唯一接口
 *     具体实现见 ./modal/templates/ 各子模块。
 */
import { BandMergeTemplate }    from './modal/templates/BandMergeTemplate.js';
import { BandExtractTemplate }  from './modal/templates/BandExtractTemplate.js';
import { IndexTemplate }        from './modal/templates/IndexTemplate.js';
import { ExtractionTemplate }   from './modal/templates/ExtractionTemplate.js';
import { CalculatorTemplate }   from './modal/templates/CalculatorTemplate.js';
import { ScriptTemplate }       from './modal/templates/ScriptTemplate.js';
import { AITemplate }           from './modal/templates/AITemplate.js';
import { VectorAttrTemplate }   from './modal/templates/VectorAttrTemplate.js';
import { RasterAttrTemplate }   from './modal/templates/RasterAttrTemplate.js';
import { DetailTemplate }       from './modal/templates/DetailTemplate.js';
import {
    esc,
    attrBadgeCls,
    attrTypeIcon,
    attrFmtVal,
    renderSelectOptions,
    renderActionLoading,
} from './modal/utils.js';

export const ModalComponent = {
    renderMergeList:             (...a) => BandMergeTemplate.renderMergeList(...a),
    renderExtractList:           (...a) => BandExtractTemplate.renderExtractList(...a),
    renderExtractSourceList:     (...a) => BandExtractTemplate.renderExtractSourceList(...a),
    renderIndexConfig:           (...a) => IndexTemplate.renderIndexConfig(...a),
    renderExtractionConfig:      (...a) => ExtractionTemplate.renderExtractionConfig(...a),
    renderCalculatorVariables:   (...a) => CalculatorTemplate.renderCalculatorVariables(...a),
    renderScriptEditor:          (...a) => ScriptTemplate.renderScriptEditor(...a),
    renderAITargetOptions:       (...a) => AITemplate.renderAITargetOptions(...a),
    renderAttrTableHead:         (...a) => VectorAttrTemplate.renderAttrTableHead(...a),
    renderAttrTableBody:         (...a) => VectorAttrTemplate.renderAttrTableBody(...a),
    renderAttrTableLoading:      ()     => VectorAttrTemplate.renderAttrTableLoading(),
    renderRasterFieldTableHead:  ()     => RasterAttrTemplate.renderRasterFieldTableHead(),
    renderRasterFieldTableBody:  (...a) => RasterAttrTemplate.renderRasterFieldTableBody(...a),
    renderDetail:                (...a) => DetailTemplate.renderDetail(...a),
    renderSelectOptions,
    renderActionLoading,
    _esc:          esc,
    _attrBadgeCls: attrBadgeCls,
    _attrTypeIcon: attrTypeIcon,
    _attrFmtVal:   attrFmtVal,
};
