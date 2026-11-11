import { Marked } from '../../../../vendor/markdown/marked.js';
import DOMPurify from '../../../../vendor/markdown/purify.js';

const escapeHTML = (value) => String(value).replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[char]);
const parser = new Marked({
    gfm: true, breaks: true,
    renderer: {
        html({ text }) { return escapeHTML(text); },
        // Do not fetch tracking images embedded in model output or saved chats.
        image({ text }) { return escapeHTML(text); },
    },
});

export function renderAgentMarkdown(value = '') {
    const fragment = DOMPurify.sanitize(parser.parse(String(value).replace(/^[\u200B-\u200F\uFEFF]+/, '')), {
        RETURN_DOM_FRAGMENT: true,
        ALLOWED_TAGS: ['p', 'br', 'hr', 'strong', 'em', 'del', 's', 'blockquote', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'pre', 'code', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'a', 'input'],
        ALLOWED_ATTR: ['href', 'title', 'class', 'start', 'align', 'type', 'checked', 'disabled'],
        ALLOW_DATA_ATTR: false,
    });
    for (const link of fragment.querySelectorAll('a')) {
        const href = link.getAttribute('href') || '';
        if (!/^(https?:\/\/|mailto:|#|\/(?!\/))/i.test(href)) link.removeAttribute('href');
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
    }
    for (const input of fragment.querySelectorAll('input')) {
        if (input.type !== 'checkbox') input.remove();
        else input.disabled = true;
    }
    const wrapper = document.createElement('div');
    wrapper.className = 'ai-markdown';
    wrapper.append(fragment);
    return wrapper.outerHTML;
}
