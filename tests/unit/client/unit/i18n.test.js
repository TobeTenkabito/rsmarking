import { afterEach, describe, expect, it } from 'vitest';

import {
    getDateLocale,
    getLanguage,
    setLanguage,
    t,
} from '@app/i18n/index.js';
import { AIModule } from '@app/modules/AIModule.js';
import { aiModal } from '../../../../client/packages/ui/src/templates/modals/aiModal.js';


describe('website language support', () => {
    afterEach(() => {
        setLanguage('en');
        document.body.innerHTML = '';
        localStorage.clear();
    });

    it('switches interface text and locale to Japanese', () => {
        document.body.innerHTML = `
            <select id="app-language-select">
                <option value="zh">中文</option>
                <option value="en">English</option>
                <option value="ja">日本語</option>
                <option value="es">Español</option>
            </select>
            <span id="translated">空间裁剪</span>
            <input id="prompt" placeholder="Example: Analyze vegetation coverage in this image\nOr: Rename the layer to something more descriptive">
        `;

        setLanguage('ja-JP');

        expect(getLanguage()).toBe('ja');
        expect(getDateLocale()).toBe('ja-JP');
        expect(document.documentElement.lang).toBe('ja');
        expect(document.getElementById('app-language-select').value).toBe('ja');
        expect(document.getElementById('translated').textContent).toBe('空間クリップ');
        expect(document.getElementById('prompt').placeholder).toContain('植生被覆');
        expect(t('nav.layerCounter', { count: 3 })).toBe('読み込み済みレイヤー: 3');
    });

    it('switches previously translated nodes to Spanish', () => {
        document.body.innerHTML = '<span id="translated">空间裁剪</span>';

        setLanguage('ja');
        setLanguage('es-MX');

        expect(getLanguage()).toBe('es');
        expect(getDateLocale()).toBe('es-ES');
        expect(document.documentElement.lang).toBe('es');
        expect(document.getElementById('translated').textContent).toBe('Recorte espacial');
        expect(t('draw.active', { tool: 'Polígono' })).toBe('Dibujando: Polígono');
        expect(localStorage.getItem('rsmarking.ui.language')).toBe('es');
    });

    it('offers all supported AI output languages exactly once', () => {
        const values = [...aiModal.matchAll(/<option value="(zh|en|ja|es)">/g)]
            .map((match) => match[1]);

        expect(values).toEqual(['zh', 'en', 'ja', 'es']);
        expect(aiModal).toContain('日本語');
        expect(aiModal).toContain('Español');
    });

    it('uses the interface language as the AI output language', () => {
        document.body.innerHTML = `
            <div id="ai-modal" class="hidden"></div>
            <select id="ai-target-select"></select>
            <select id="ai-language-select">
                <option value="zh">中文</option>
                <option value="en">English</option>
                <option value="ja">日本語</option>
                <option value="es">Español</option>
            </select>
        `;
        const ai = new AIModule({});
        ai._bindModalEvents = () => {};
        ai._syncDataTypeWithTarget = () => {};
        ai._syncModeUI = () => {};
        ai._renderFunctionCatalog = () => {};
        ai.loadFunctionCatalog = async () => {};
        ai.loadConversationArchives = async () => {};

        setLanguage('es');
        ai.openModal();

        expect(document.getElementById('ai-language-select').value).toBe('es');
    });
});
