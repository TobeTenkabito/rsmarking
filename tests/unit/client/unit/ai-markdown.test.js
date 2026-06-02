import { afterEach, describe, expect, it, vi } from 'vitest';

import { AIModule } from '@app/modules/AIModule.js';
import { AIAPI } from '@app/api/ai.js';


describe('AIModule markdown rendering', () => {
    afterEach(() => {
        vi.restoreAllMocks();
        document.body.innerHTML = '';
    });

    it('renders common markdown while escaping raw html', () => {
        const ai = new AIModule({});
        const html = ai._renderMarkdown([
            '# Summary',
            '',
            '- **NDVI** looks healthy',
            '- Use `calculate_ndvi`',
            '',
            '| Raster | Status |',
            '| --- | --- |',
            '| A | good |',
            '',
            '```python',
            "print('<unsafe>')",
            '```',
            '',
            '<script>alert(1)</script>',
        ].join('\n'));

        expect(html).toContain('<h1');
        expect(html).toContain('<strong>NDVI</strong>');
        expect(html).toContain('<code class=');
        expect(html).toContain('<table');
        expect(html).toContain('&lt;unsafe&gt;');
        expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
        expect(html).not.toContain('<script>');
    });

    it('drops unsafe markdown links', () => {
        const ai = new AIModule({});
        const html = ai._renderMarkdown('[bad](javascript:alert(1)) [good](https://example.com)');

        expect(html).not.toContain('javascript:alert');
        expect(html).toContain('https://example.com');
    });

    it('renders agent attachment previews and pending state', () => {
        const ai = new AIModule({});
        const html = ai._renderAgentMessage({
            role: 'user',
            content: 'Please inspect this.',
            attachments: [
                {
                    name: 'scene.png',
                    kind: 'image',
                    mime_type: 'image/png',
                    size: 100,
                    image_data_url: 'data:image/png;base64,AAAA',
                    width: 10,
                    height: 10,
                },
                {
                    name: 'notes.md',
                    kind: 'text',
                    mime_type: 'text/markdown',
                    size: 24,
                },
            ],
        });
        const pending = ai._renderAgentMessage({ role: 'assistant', pending: true });

        expect(html).toContain('scene.png');
        expect(html).toContain('notes.md');
        expect(html).toContain('data:image/png;base64,AAAA');
        expect(pending).toContain('Waiting for AI response');
    });

    it('renders assistant output verbatim after completion', () => {
        const ai = new AIModule({});
        const html = ai._renderAgentMessage({
            role: 'assistant',
            content: '**not bold**\nline <unsafe>',
        });

        expect(html).toContain('**not bold**');
        expect(html).toContain('line &lt;unsafe&gt;');
        expect(html).not.toContain('<strong>');
        expect(html).toContain('whitespace-pre-wrap');
    });

    it('renders the user message before the agent request resolves', async () => {
        document.body.innerHTML = `
            <textarea id="ai-prompt-input">Hello</textarea>
            <div id="ai-agent-messages"></div>
            <div id="ai-agent-session-label"></div>
            <div id="ai-agent-attachment-list"></div>
        `;
        const ai = new AIModule({});
        vi.spyOn(AIAPI, 'agent').mockImplementation(async () => {
            expect(document.getElementById('ai-agent-messages').innerHTML).toContain('Hello');
            expect(document.getElementById('ai-agent-messages').innerHTML).toContain('Waiting for AI response');
            return {
                session_id: 'session-a',
                answer: 'Done.',
                steps: [],
                used_tools: [],
            };
        });

        await ai._runAgent({ user_prompt: 'Hello', attachments: [] });

        const html = document.getElementById('ai-agent-messages').innerHTML;
        expect(html).toContain('Hello');
        expect(html).toContain('Done.');
        expect(html).not.toContain('Waiting for AI response');
    });

    it('queues agent requests so only one backend call runs at a time', async () => {
        document.body.innerHTML = `
            <textarea id="ai-prompt-input"></textarea>
            <div id="ai-agent-messages"></div>
            <div id="ai-agent-session-label"></div>
            <div id="ai-agent-attachment-list"></div>
        `;
        const ai = new AIModule({});
        let resolveFirst;
        let resolveSecond;
        vi.spyOn(AIAPI, 'agent')
            .mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve; }))
            .mockImplementationOnce(() => new Promise(resolve => { resolveSecond = resolve; }));

        const first = ai._runAgent({ user_prompt: 'First', attachments: [] });
        const second = ai._runAgent({ user_prompt: 'Second', attachments: [] });
        await new Promise(resolve => setTimeout(resolve, 0));

        expect(AIAPI.agent).toHaveBeenCalledTimes(1);
        expect(document.getElementById('ai-agent-messages').innerHTML).toContain('Queued');

        resolveFirst({ session_id: 'session-a', answer: 'First answer', steps: [], used_tools: [] });
        await first;
        await Promise.resolve();

        expect(AIAPI.agent).toHaveBeenCalledTimes(2);

        resolveSecond({ session_id: 'session-a', answer: 'Second answer', steps: [], used_tools: [] });
        await second;

        const html = document.getElementById('ai-agent-messages').innerHTML;
        expect(html).toContain('First answer');
        expect(html).toContain('Second answer');
    });
});
