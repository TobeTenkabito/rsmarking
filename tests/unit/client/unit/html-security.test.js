import { afterEach, describe, expect, it, vi } from 'vitest';
import { SidebarComponent } from '../../../../client/packages/ui/src/components/Sidebar.js';
import { ModalComponent } from '../../../../client/packages/ui/src/components/Modal.js';
import { AttributeTable } from '@app/modules/AttributeTable.js';
import { AnalysisModule } from '@app/modules/AnalysisModule.js';
import { UIManager } from '@app/core/UIManager.js';
import { jsArg } from '../../../../client/packages/ui/src/components/modal/utils.js';

const markup = '<img data-xss="yes" src="x" onerror="globalThis.__xss=true">';
const code = `O'Reilly");globalThis.__xss=true;//\\\n${markup}`;
const raster = { id: 1, index_id: 10, file_name: markup, bands: 1, data_type: 'Float32', crs: markup };
const field = { id: 'field-1', field_name: markup, field_alias: code, field_type: 'string', is_system: false };

function mount(html, table = false) {
    const node = document.createElement(table ? 'table' : 'div');
    node.innerHTML = html;
    expect(node.querySelector('[data-xss]')).toBeNull();
    return node;
}

function invoke(node, eventName, rs) {
    // Evaluate the browser-decoded attribute, exercising both HTML and JS contexts.
    new Function('RS', 'event', node.getAttribute(eventName)).call(node, rs, { stopPropagation() {} });
    expect(globalThis.__xss).toBe(false);
}

afterEach(() => {
    document.body.innerHTML = '';
    delete globalThis.__xss;
    vi.restoreAllMocks();
    vi.useRealTimers();
});

describe('Untrusted GIS metadata rendering', () => {
    it.each(["');globalThis.__xss=true;//", `quotes'"\\\n中文`, markup])('encodes event arguments through HTML decoding: %s', (value) => {
        globalThis.__xss = false;
        const node = mount(`<button onclick="RS.accept(${jsArg(value)})">Open</button>`);
        const accept = vi.fn();
        invoke(node.querySelector('button'), 'onclick', { accept });
        expect(accept).toHaveBeenCalledWith(value);
    });

    it('escapes loading and toast messages', () => {
        vi.useFakeTimers();
        const ui = new UIManager({});
        ui.showGlobalLoading(markup);
        ui.showToast(markup, 'error');
        expect(document.querySelector('[data-xss]')).toBeNull();
        expect(document.getElementById('global-loader').textContent).toContain(markup);
        expect(document.body.textContent).toContain(markup);
    });

    it('renders spectral band names and error messages as text', () => {
        document.body.innerHTML = '<div id="map"></div>';
        const analysis = new AnalysisModule({});
        analysis._showSpectrumPanel({ bands: [{ name: markup, value: 1 }], coordinate: { lng: 0, lat: 0 } });
        expect(document.querySelector('[data-xss]')).toBeNull();
        expect(document.getElementById('spectrum-panel').textContent).toContain(markup);
        analysis._showSpectrumPanel(null, markup);
        expect(document.querySelector('[data-xss]')).toBeNull();
        expect(document.getElementById('spectrum-panel').textContent).toContain(markup);
    });

    it('renders raster, project and layer names as text in the sidebar', () => {
        const project = { id: 'project-1', name: markup };
        const layer = { id: 'layer-1', name: markup };
        const node = mount(SidebarComponent.render({
            rasters: [raster], activeLayerIds: new Set(), loadingIds: new Set(),
            projects: [project], activeProject: project, vectorLayers: [layer], visibleVectorLayerIds: new Set(),
        }));
        expect(node.textContent).toContain(markup);
    });

    it.each(['__proto__', 'constructor', 'toString'])('accepts bundle name %s without reading object prototypes', (bundle_id) => {
        const node = mount(SidebarComponent.renderRasterSection([{ ...raster, bundle_id }], new Set(), new Set()));
        expect(node.querySelector('.layer-item')).not.toBeNull();
    });

    it.each([
        () => ModalComponent.renderMergeList([raster], []),
        () => ModalComponent.renderExtractList(raster, []),
        () => ModalComponent.renderExtractSourceList([raster], null),
        () => ModalComponent.renderCalculatorVariables(['A'], [raster]),
        () => ModalComponent.renderSelectOptions([raster]),
        () => ModalComponent.renderDetail(raster),
    ])('escapes metadata in imagery templates %#', (render) => {
        expect(mount(render()).textContent).toContain(markup);
    });

    it('preserves script text without allowing it to close the textarea', () => {
        const script = `print("x")\n</textarea>${markup}`;
        const node = mount(ModalComponent.renderScriptEditor([raster], [], script));
        expect(node.querySelector('textarea').value).toBe(script);
    });

    it('renders property values and column aliases as text', () => {
        const header = mount(ModalComponent.renderAttrTableHead([field]), true);
        expect(header.textContent).toContain(code);
        const body = mount(ModalComponent.renderAttrTableBody([{ id: 'feature-1', properties: { [markup]: markup } }], [field]), true);
        expect(body.querySelector('.cell-val').textContent).toBe(markup);
    });

    it('round-trips raster and vector names through decoded click handlers', () => {
        globalThis.__xss = false;
        const openRaster = vi.fn();
        const rasterNode = mount(SidebarComponent.renderItem({ ...raster, file_name: code }, false, false));
        const rasterButton = [...rasterNode.querySelectorAll('button')].find(node => node.getAttribute('onclick')?.includes('openAttriRaster'));
        invoke(rasterButton, 'onclick', { openAttriRaster: openRaster });
        expect(openRaster).toHaveBeenCalledWith('10', code);
        const openVector = vi.fn();
        const vectorNode = mount(SidebarComponent.renderVectorItem({ id: 'layer-1', name: code }, false, false));
        const vectorButton = [...vectorNode.querySelectorAll('button')].find(node => node.getAttribute('onclick')?.includes('openAttriVector'));
        invoke(vectorButton, 'onclick', { openAttriVector: openVector });
        expect(openVector).toHaveBeenCalledWith('layer-1', code);
    });

    it('round-trips column aliases and raster field names through event handlers', () => {
        globalThis.__xss = false;
        const rename = vi.fn();
        const header = mount(ModalComponent.renderAttrTableHead([field]), true);
        invoke(header.querySelector('[ondblclick]'), 'ondblclick', { attrRenameColumn: rename });
        expect(rename).toHaveBeenCalledWith(field.id, code);
        const renameRaster = vi.fn();
        const body = mount(ModalComponent.renderRasterFieldTableBody([field]), true);
        invoke(body.querySelector('[ondblclick]'), 'ondblclick', { attrrenameRasterField: renameRaster });
        expect(renameRaster).toHaveBeenCalledWith(field.id, code);
    });

    it('keeps context-menu field names as arguments instead of executable code', () => {
        globalThis.__xss = false;
        const table = new AttributeTable({});
        table.showColumnMenu({ preventDefault() {}, clientX: 0, clientY: 0 }, 'field-1', code, false);
        const rename = vi.fn();
        invoke(document.querySelector('.ctx-item'), 'onclick', { attrRenameColumn: rename });
        expect(rename).toHaveBeenCalledWith('field-1', code);
        expect(document.querySelector('[data-xss]')).toBeNull();
        table._hideCtxMenu();
    });
});
