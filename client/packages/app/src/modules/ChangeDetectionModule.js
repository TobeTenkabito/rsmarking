/**
 * ChangeDetectionModule - 变化检测模块
 */
import { ChangeAPI } from '../api/change.js';
import { Store }     from '../store/index.js';

export class ChangeDetectionModule {
  constructor(app) {
    this.app         = app;
    this.method      = 'band-diff';
    this._lastResult = null;

  this._onIndexChange = (e) => {
    if (e.target.id !== 'change-index-select') return;
    const hints = {
      ndvi:  'NDVI：B1 = Red，B2 = NIR',
      ndwi:  'NDWI：B1 = Green，B2 = NIR',
      ndbi:  'NDBI：B1 = SWIR，B2 = NIR',
      mndwi: 'MNDWI：B1 = Green，B2 = SWIR',
    };
    const el = document.getElementById('change-index-band-hint');
    if (el) el.textContent = hints[e.target.value] ?? '';
  };

  document.addEventListener('change', this._onIndexChange);
}


  open() {
    const modal = document.getElementById('change-modal');
    if (!modal) return;
    this._renderRasterOptions();
    this._resetResult();
    this._setStatus('选择两期影像后执行分析');
    modal.classList.remove('hidden');
  }

  close() {
    document.getElementById('change-modal')?.classList.add('hidden');
  }


  switchMethod(method) {
    this.method = method;

    document.querySelectorAll('.change-method-tab').forEach(btn => {
      const isActive = btn.dataset.method === method;
      btn.classList.toggle('border-orange-500',  isActive);
      btn.classList.toggle('text-orange-600',    isActive);
      btn.classList.toggle('bg-orange-50',       isActive);
      btn.classList.toggle('border-transparent', !isActive);
      btn.classList.toggle('text-slate-400',     !isActive);
    });

    const isIndex = method === 'index-diff';
    document.getElementById('change-params-band') ?.classList.toggle('hidden', isIndex);
    document.getElementById('change-params-index')?.classList.toggle('hidden', !isIndex);

    // 阈值提示 & 默认值
    const hint = document.getElementById('change-threshold-hint');
    if (hint) hint.textContent = method === 'band-ratio' ? '（偏离 1.0 的幅度）' : '（差值绝对值）';

    const thresholdInput = document.getElementById('change-threshold-input');
    if (thresholdInput) thresholdInput.value = method === 'band-ratio' ? '0.2' : '0.1';

    this._resetResult();
  }

  async run() {
    const t1Id = Number(document.getElementById('change-t1-select')?.value);
    const t2Id = Number(document.getElementById('change-t2-select')?.value);

    if (!t1Id || !t2Id) {
      this.app.ui.showToast('请先选择 T1 和 T2 两期影像', 'warning');
      return;
    }
    if (t1Id === t2Id) {
      this.app.ui.showToast('T1 与 T2 不能是同一幅影像', 'warning');
      return;
    }

    this._setRunning(true);
    this._resetResult();
    this.app.ui.showGlobalLoading('变化检测运算中...');

    try {
      let result;
      const thresholdMode = document.getElementById('change-threshold-mode')?.value ?? 'abs';

      if (this.method === 'band-diff') {
        result = await ChangeAPI.bandDiff(t1Id, t2Id, {
          bandIdx:       Number(document.getElementById('change-band-input')?.value ?? 1),
          threshold:     Number(document.getElementById('change-threshold-input')?.value ?? 0.1),
          thresholdMode,
          outputMask:    true,
        });

      } else if (this.method === 'band-ratio') {
        result = await ChangeAPI.bandRatio(t1Id, t2Id, {
          bandIdx:    Number(document.getElementById('change-band-input')?.value ?? 1),
          threshold:  Number(document.getElementById('change-threshold-input')?.value ?? 0.2),
          outputMask: true,
        });

      } else {
        // index-diff：需要 4 个波段 index_id
        const t1b1 = Number(document.getElementById('change-t1-b1-select')?.value);
        const t1b2 = Number(document.getElementById('change-t1-b2-select')?.value);
        const t2b1 = Number(document.getElementById('change-t2-b1-select')?.value);
        const t2b2 = Number(document.getElementById('change-t2-b2-select')?.value);

        if (!t1b1 || !t1b2 || !t2b1 || !t2b2) {
          this.app.ui.showToast('指数差值法需要为 T1/T2 各选择两个波段', 'warning');
          this._setRunning(false);
          this.app.ui.hideGlobalLoading();
          return;
        }

        result = await ChangeAPI.indexDiff(
          { b1: t1b1, b2: t1b2 },
          { b1: t2b1, b2: t2b2 },
          {
            indexType:     document.getElementById('change-index-select')?.value ?? 'ndvi',
            threshold:     Number(document.getElementById('change-index-threshold-input')?.value ?? 0.15),
            thresholdMode,
            outputMask:    true,
          }
        );
      }

      this._lastResult = result;
      this._showResult(result);
      this._setStatus(this._buildStatText(result));
      this.app.ui.showToast('变化检测完成', 'success');

    } catch (err) {
      console.error('[ChangeDetection] 运行失败:', err);
      this._setStatus(`✗ ${err.message}`);
      this.app.ui.showToast(`检测失败：${err.message}`, 'error');
    } finally {
      this._setRunning(false);
      this.app.ui.hideGlobalLoading();
    }
  }


  /**
   * 加载差值图 + 可选掩膜到地图
   * @param {'diff'|'mask'} which - 加载哪一层，默认 diff
   */
  async loadResultToMap(which = 'diff') {
    if (!this._lastResult) return;

    const indexId = which === 'mask'
      ? this._lastResult.mask_index_id
      : this._lastResult.diff_index_id;

    if (!indexId) {
      this.app.ui.showToast('该结果图层不存在', 'warning');
      return;}

  try {
    await this.app.raster.refreshData();
    const raster = Store.getRasters().find(r => r.index_id === indexId);
    if (!raster) {
      this.app.ui.showToast('结果图层未找到，请稍后重试', 'warning');
      return;
    }
    await this.app.mapController.toggleLayer(raster.id);

    this.app.ui.showToast(
      `已加载${which === 'mask' ? '变化掩膜' : '差值图'}`,
      'success'
    );
    this.close();

  } catch (err) {
    console.error('[ChangeDetection] 加载图层失败:', err);
    this.app.ui.showToast(`加载失败：${err.message}`, 'error');
  }
}


  _renderRasterOptions() {
    const rasters = Store.getRasters();
    const opts = rasters.length
      ? rasters.map(r =>
          `<option value="${r.index_id ?? r.id}">
             ${r.file_name ?? r.name}
             ${r.bands ? `（${r.bands} 波段）` : ''}
           </option>`
        ).join('')
      : '<option value="" disabled>暂无可用影像</option>';

    const placeholder = '<option value="">— 请选择 —</option>';
    ['change-t1-select','change-t2-select',
     'change-t1-b1-select','change-t1-b2-select',
     'change-t2-b1-select','change-t2-b2-select'].forEach(id => {
      const el = document.getElementById(id);
      if (el) el.innerHTML = placeholder + opts;
    });
  }

  _showResult(result) {
    const area = document.getElementById('change-result-area');
    if (area) area.classList.remove('hidden');
    const diffBtn = document.getElementById('change-load-diff-btn');
    if (diffBtn) diffBtn.classList.toggle('hidden', !result.diff_index_id);
    const maskBtn = document.getElementById('change-load-mask-btn');
    if (maskBtn) maskBtn.classList.toggle('hidden', !result.mask_index_id);
  }

  _resetResult() {
    document.getElementById('change-result-area')?.classList.add('hidden');
    this._lastResult = null;
  }

  _setStatus(text) {
    const el = document.getElementById('change-status-text');
    if (el) el.textContent = text;
  }

  _setRunning(isRunning) {
    const btn = document.getElementById('change-run-btn');
    if (!btn) return;
    btn.disabled    = isRunning;
    btn.textContent = isRunning ? '运算中...' : '执行分析';
  }

  /** 根据后端统计字段生成状态文字 */
  _buildStatText(result) {
    const parts = ['✓ 检测完成'];
    if (result.change_pixel_count != null) {
      parts.push(`变化像元 ${result.change_pixel_count.toLocaleString()} 个`);
    }
    if (result.change_area_ratio != null) {
      parts.push(`占比 ${(result.change_area_ratio * 100).toFixed(1)}%`);
    }
    return parts.join('　');
  }
}
