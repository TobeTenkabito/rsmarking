/**
 * ChangeDetectionModule - Change DetectionEnglish
 */
import { ChangeAPI } from '../api/change.js';
import { Store }     from '../store/index.js';

const INDEX_BAND_HINTS = {
  ndvi:  'NDVI: B1 = Red, B2 = NIR',
  ndwi:  'NDWI: B1 = Green, B2 = NIR',
  ndbi:  'NDBI: B1 = SWIR, B2 = NIR',
  mndwi: 'MNDWI: B1 = Green, B2 = SWIR',
};

export class ChangeDetectionModule {
  constructor(app) {
    this.app         = app;
    this.method      = 'band-diff';
    this._lastResult = null;

  this._onIndexChange = (e) => {
    if (e.target.id !== 'change-index-select') return;
    /*
      ndvi:  'NDVI：B1 = Red，B2 = NIR',
      ndwi:  'NDWI：B1 = Green，B2 = NIR',
      ndbi:  'NDBI：B1 = SWIR，B2 = NIR',
      mndwi: 'MNDWI：B1 = Green，B2 = SWIR',
    */
    const el = document.getElementById('change-index-band-hint');
    if (el) el.textContent = INDEX_BAND_HINTS[e.target.value] ?? '';
  };

  document.addEventListener('change', this._onIndexChange);
}


  open() {
    const modal = document.getElementById('change-modal');
    if (!modal) return;
    this._renderRasterOptions();
    this._resetResult();
    this._setStatus('Select two imagery dates, then run analysis.');
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

    // English & Default Value
    const hint = document.getElementById('change-threshold-hint');
    if (hint) hint.textContent = method === 'band-ratio' ? '(distance from 1.0)' : '(absolute difference)';

    const thresholdInput = document.getElementById('change-threshold-input');
    if (thresholdInput) thresholdInput.value = method === 'band-ratio' ? '0.2' : '0.1';

    this._resetResult();
  }

  async run() {
    const t1Id = Number(document.getElementById('change-t1-select')?.value);
    const t2Id = Number(document.getElementById('change-t2-select')?.value);

    if (!t1Id || !t2Id) {
      this.app.ui.showToast('Select both T1 and T2 imagery.', 'warning');
      return;
    }
    if (t1Id === t2Id) {
      this.app.ui.showToast('T1 and T2 cannot be the same image.', 'warning');
      return;
    }

    this._setRunning(true);
    this._resetResult();
    this.app.ui.showGlobalLoading('Running change detection...');

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
        // index-diff：English 4 Englishbands index_id
        const t1b1 = Number(document.getElementById('change-t1-b1-select')?.value);
        const t1b2 = Number(document.getElementById('change-t1-b2-select')?.value);
        const t2b1 = Number(document.getElementById('change-t2-b1-select')?.value);
        const t2b2 = Number(document.getElementById('change-t2-b2-select')?.value);

        if (!t1b1 || !t1b2 || !t2b1 || !t2b2) {
          this.app.ui.showToast('Index difference requires two bands for both T1 and T2.', 'warning');
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
      this.app.ui.showToast('Change detection complete.', 'success');

    } catch (err) {
      console.error('[ChangeDetection] Run failed:', err);
      this._setStatus(`✗ ${err.message}`);
      this.app.ui.showToast(`Detection failed：${err.message}`, 'error');
    } finally {
      this._setRunning(false);
      this.app.ui.hideGlobalLoading();
    }
  }


  /**
   * load difference raster + OptionalEnglish
   * @param {'diff'|'mask'} which - English，English diff
   */
  async loadResultToMap(which = 'diff') {
    if (!this._lastResult) return;

    const indexId = which === 'mask'
      ? this._lastResult.mask_index_id
      : this._lastResult.diff_index_id;

    if (!indexId) {
      this.app.ui.showToast('That result layer does not exist.', 'warning');
      return;}

  try {
    await this.app.raster.refreshData();
    const raster = Store.getRasters().find(r => r.index_id === indexId);
    if (!raster) {
      this.app.ui.showToast('Result layer not found. Try again later.', 'warning');
      return;
    }
    await this.app.mapController.toggleLayer(raster.id);

    this.app.ui.showToast(
      `Loaded ${which === 'mask' ? 'change mask' : 'difference raster'}`,
      'success'
    );
    this.close();

  } catch (err) {
    console.error('[ChangeDetection] Layer load failed:', err);
    this.app.ui.showToast(`Load failed：${err.message}`, 'error');
  }
}


  _renderRasterOptions() {
    const rasters = Store.getRasters();
    const opts = rasters.length
      ? rasters.map(r =>
          `<option value="${r.index_id ?? r.id}">
             ${r.file_name ?? r.name}
             ${r.bands ? `（${r.bands} bands）` : ''}
           </option>`
        ).join('')
      : '<option value="" disabled>No available imagery</option>';

    const placeholder = '<option value="">-- Select --</option>';
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
    btn.textContent = isRunning ? 'Running...' : 'Run Analysis';
  }

  /** English */
  _buildStatText(result) {
    const parts = ['✓ Detection Complete'];
    if (result.change_pixel_count != null) {
      parts.push(`Changed pixels ${result.change_pixel_count.toLocaleString()}`);
    }
    if (result.change_area_ratio != null) {
      parts.push(`Share ${(result.change_area_ratio * 100).toFixed(1)}%`);
    }
    return parts.join('　');
  }
}
