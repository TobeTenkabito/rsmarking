import { beforeEach, afterEach, describe, expect, it, vi } from 'vitest';
import { AIModule } from '@app/modules/AIModule.js';
import { AIAPI } from '@app/api/ai.js';
import { setLanguage, applyTranslations } from '@app/i18n/index.js';
import { aiModal } from '../../../../client/packages/ui/src/templates/modals/aiModal.js';

describe('Agent workspace interactions', () => {
    let ai;
    beforeEach(() => {
        localStorage.clear();
        setLanguage('en');
        document.body.innerHTML = aiModal;
        ai = new AIModule({});
        ai._bindModalEvents();
    });
    afterEach(() => { vi.restoreAllMocks(); document.body.innerHTML = ''; });
    const key = (input, options = {}) => input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true, cancelable: true, ...options }));

    it('sends on Enter, inserts Ctrl+Enter at the caret and respects IME/Shift/repeat', () => {
        const execute = vi.spyOn(ai, 'execute').mockResolvedValue();
        const input = document.getElementById('ai-prompt-input');
        input.value = 'hello world'; input.setSelectionRange(5, 5);
        key(input, { isComposing: true }); key(input, { shiftKey: true }); key(input, { repeat: true });
        expect(execute).not.toHaveBeenCalled();
        key(input, { ctrlKey: true });
        expect(input.value).toBe('hello\n world');
        key(input);
        expect(execute).toHaveBeenCalledTimes(1);
    });

    it('persists the alternate shortcut and supports Command on macOS', () => {
        const execute = vi.spyOn(ai, 'execute').mockResolvedValue();
        const mode = document.getElementById('ai-send-mode');
        mode.value = 'ctrl-enter'; mode.dispatchEvent(new Event('change'));
        const input = document.getElementById('ai-prompt-input');
        key(input); expect(execute).not.toHaveBeenCalled();
        key(input, { metaKey: true }); expect(execute).toHaveBeenCalledTimes(1);
        expect(new AIModule({})._sendMode).toBe('ctrl-enter');
    });

    it('ignores duplicate sends while busy and preserves the draft', () => {
        const execute = vi.spyOn(ai, 'execute').mockResolvedValue();
        ai._loadingDepth = 1;
        const input = document.getElementById('ai-prompt-input'); input.value = 'draft';
        key(input);
        expect(execute).not.toHaveBeenCalled(); expect(input.value).toBe('draft');
    });

    it('keeps searchable history visible and renders titles as text', () => {
        ai._conversationArchives = [{ archive_id: 'a'.repeat(32), title: '<img src=x onerror=alert(1)> Terrain' }];
        ai._renderArchivePanel();
        const panel = document.getElementById('ai-agent-archive-panel');
        expect(panel.classList.contains('hidden')).toBe(false);
        expect(panel.querySelector('img')).toBeNull();
        const search = document.getElementById('ai-history-search'); search.value = 'missing'; search.dispatchEvent(new Event('input'));
        expect(panel.querySelector('[data-ai-open-chat]')).toBeNull();
        search.value = 'terrain'; search.dispatchEvent(new Event('input'));
        expect(panel.querySelectorAll('[data-ai-open-chat]')).toHaveLength(1);
    });

    it('serializes saves and retries the same archive identity without duplicates', async () => {
        let release;
        const save = vi.spyOn(AIAPI, 'archiveConversation')
            .mockImplementationOnce(() => new Promise(resolve => { release = resolve; }))
            .mockImplementation(async payload => ({ conversation: { ...payload, message_count: payload.messages.length } }));
        ai._agentConversation = [{ role: 'user', content: 'terrain' }];
        const first = ai._saveConversation();
        ai._agentConversation.push({ role: 'assistant', content: 'done' });
        const second = ai._saveConversation();
        await new Promise(resolve => setTimeout(resolve, 0));
        expect(save).toHaveBeenCalledTimes(1);
        release({ conversation: save.mock.calls[0][0] });
        await first; await second;
        expect(save.mock.calls[0][0].messages).toHaveLength(1);
        expect(save.mock.calls[1][0].messages).toHaveLength(2);
        expect(save.mock.calls[0][0].archive_id).toBe(save.mock.calls[1][0].archive_id);
        expect(ai._conversationArchives).toHaveLength(1);
    });

    it('edits titles and notes without changing the active chat, retaining drafts on failure', async () => {
        const id = 'a'.repeat(32);
        ai._conversationArchives = [{ archive_id: id, title: 'Old', note: 'Existing' }];
        const session = ai._sessionId;
        ai.editConversationDetails(id);
        const title = document.getElementById('ai-history-edit-title');
        const note = document.getElementById('ai-history-edit-note');
        title.value = 'Renamed'; title.dispatchEvent(new Event('input', { bubbles: true }));
        note.value = 'First line\nSecond line'; note.dispatchEvent(new Event('input', { bubbles: true }));
        // A background render must not discard the editor's text or focus.
        note.focus(); note.setSelectionRange(4, 4); ai._renderArchivePanel();
        expect(document.activeElement.id).toBe('ai-history-edit-note');
        expect(document.activeElement.selectionStart).toBe(4);
        const update = vi.spyOn(AIAPI, 'updateConversation').mockRejectedValueOnce(new Error('offline'))
            .mockResolvedValueOnce({ conversation: { archive_id: id, title: 'Renamed', note: 'First line\nSecond line' } });
        expect(await ai.saveConversationDetails()).toBe(false);
        expect(document.getElementById('ai-history-edit-note').value).toBe('First line\nSecond line');
        expect(document.querySelector('.ai-history-edit-error')).not.toBeNull();
        expect(await ai.saveConversationDetails()).toBe(true);
        expect(update).toHaveBeenLastCalledWith(id, { title: 'Renamed', note: 'First line\nSecond line' });
        expect(ai._sessionId).toBe(session);
        expect(ai._conversationArchives[0].title).toBe('Renamed');
        expect(document.querySelector('[data-ai-edit-form]')).toBeNull();
    });

    it('renders notes safely, expands on click, collapses on leaving, and searches notes', () => {
        ai._conversationArchives = [{ archive_id: 'a'.repeat(32), title: 'Title', note: '<img src=x onerror=alert(1)>\nNeedle' }];
        ai._renderArchivePanel();
        const note = document.querySelector('[data-ai-note]');
        const open = vi.spyOn(ai, 'loadConversationArchive');
        expect(note.querySelector('img')).toBeNull();
        expect(note.textContent).toContain('<img');
        note.click(); expect(note.getAttribute('aria-expanded')).toBe('true');
        expect(open).not.toHaveBeenCalled();
        note.dispatchEvent(new MouseEvent('pointerout', { bubbles: true, relatedTarget: document.body }));
        expect(note.getAttribute('aria-expanded')).toBe('false');
        const search = document.getElementById('ai-history-search');
        search.value = 'needle'; search.dispatchEvent(new Event('input'));
        expect(document.querySelector('[data-ai-open-chat]')).not.toBeNull();
        ai.editConversationDetails('a'.repeat(32));
        ai._archiveEdit.title = '  ';
        ai.saveConversationDetails();
        expect(document.querySelector('.ai-history-edit-error')).not.toBeNull();
        document.querySelector('[data-ai-cancel-edit]').click();
        expect(ai._conversationArchives[0].title).toBe('Title');
    });

    it('keeps unsaved messages when saving fails during a new-chat action', async () => {
        vi.spyOn(AIAPI, 'archiveConversation').mockRejectedValue(new Error('offline'));
        ai._agentConversation = [{ role: 'user', content: 'keep me' }];
        const oldSession = ai._sessionId;
        await ai.startNewAgentChat();
        expect(ai._sessionId).toBe(oldSession);
        expect(ai._agentConversation[0].content).toBe('keep me');
        expect(document.getElementById('ai-save-status').textContent).toContain('Not saved');
    });

    it('does not switch sessions while a request is in flight', async () => {
        ai._agentQueueDepth = 1;
        const get = vi.spyOn(AIAPI, 'getConversation');
        const session = ai._sessionId;
        await ai.loadConversationArchive('a'.repeat(32)); await ai.startNewAgentChat();
        expect(get).not.toHaveBeenCalled(); expect(ai._sessionId).toBe(session);
    });

    it('restores history without hiding the sidebar or losing attachments', async () => {
        const id = 'a'.repeat(32);
        vi.spyOn(AIAPI, 'getConversation').mockResolvedValue({ conversation: { archive_id: id, session_id: 'saved', messages: [{ role: 'user', content: 'saved question', attachments: [{ kind: 'text', name: 'notes.md' }] }] } });
        vi.spyOn(AIAPI, 'restoreConversation').mockResolvedValue({});
        await ai.loadConversationArchive(id);
        expect(ai._sessionId).toBe('saved'); expect(ai._activeArchiveId).toBe(id);
        expect(ai._agentConversation[0].attachments[0].name).toBe('notes.md');
        expect(document.getElementById('ai-agent-archive-panel').classList.contains('hidden')).toBe(false);
    });

    it('sends explicit autonomy and empty tool choices, without cross-chat memory by default', () => {
        document.getElementById('ai-use-tools').checked = false;
        const payload = ai._buildRequestPayload({ mode: 'agent', prompt: 'Analyze terrain' });
        expect(payload.allow_task_steps).toBe(true);
        expect(payload.tool_names).toEqual([]);
        expect(payload.include_archive_memory).toBe(false);
    });

    it('renders nested GFM and prevents HTML, URL, and token-placeholder injection', () => {
        document.getElementById('ai-agent-messages').innerHTML = ai._renderMarkdown('## Report\n\n1. Parent\n   - **Child**\n\n- [x] Finished\n\n~~old~~\n\n[x](javascript:alert(1))\n\n![tracking](https://example.test/pixel)\n\n<img src=x onerror=alert(1)>\n\n@@CODE_0@@ `safe`');
        const output = document.querySelector('.ai-markdown');
        expect(output.querySelector('ol ul strong').textContent).toBe('Child');
        expect(output.querySelector('input').disabled).toBe(true);
        expect(output.querySelector('del').textContent).toBe('old');
        expect(output.querySelector('img')).toBeNull();
        expect(output.querySelector('[onerror]')).toBeNull();
        expect(output.querySelector('a[href^="javascript:"]')).toBeNull();
        expect(output.textContent).toContain('@@CODE_0@@');
        setLanguage('zh'); applyTranslations(output);
        expect(output.querySelector('h2').textContent).toBe('Report');
    });
});
