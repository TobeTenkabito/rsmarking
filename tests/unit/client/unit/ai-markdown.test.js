import { describe, expect, it } from 'vitest';

import { AIModule } from '@app/modules/AIModule.js';


describe('AIModule markdown rendering', () => {
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
});
