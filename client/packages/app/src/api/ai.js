import { API_CONFIG } from './config.js';

const BASE_URL = API_CONFIG.aiGatewayUrl;

function resolveAIURL(value) {
    const url = String(value || '').trim();
    if (!url) return '';
    if (/^https?:\/\//i.test(url)) return url;
    if (url.startsWith('/')) return `${BASE_URL}${url}`;
    return '';
}

async function requestAI(path, payload, fallbackMessage, method = 'POST') {
    try {
        const response = await fetch(`${BASE_URL}${path}`, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `${fallbackMessage} (${response.status})`);
        }

        return await response.json();
    } catch (error) {
        console.error(`[AIAPI] ${path} Error:`, error);
        throw error;
    }
}

async function requestAIFunctions(format = 'openai') {
    try {
        const response = await fetch(`${BASE_URL}/ai/functions?format=${encodeURIComponent(format)}`);
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `Failed to fetch AI functions (${response.status})`);
        }
        return await response.json();
    } catch (error) {
        console.error('[AIAPI] /ai/functions Error:', error);
        throw error;
    }
}

async function requestAIGet(path, fallbackMessage) {
    try {
        const response = await fetch(`${BASE_URL}${path}`);
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `${fallbackMessage} (${response.status})`);
        }
        return await response.json();
    } catch (error) {
        console.error(`[AIAPI] ${path} Error:`, error);
        throw error;
    }
}

async function requestAIDelete(path, fallbackMessage) {
    try {
        const response = await fetch(`${BASE_URL}${path}`, { method: 'DELETE' });
        if (!response.ok) {
            const err = await response.json().catch(() => ({}));
            throw new Error(err.detail || `${fallbackMessage} (${response.status})`);
        }
        return await response.json();
    } catch (error) {
        console.error(`[AIAPI] ${path} Error:`, error);
        throw error;
    }
}

export const AIAPI = {
    resolveURL(value) {
        return resolveAIURL(value);
    },

    async analyze(payload) {
        return requestAI('/ai/process', {
            ...payload,
            mode: 'analyze',
            overwrite: false,
        }, 'Analyze request failed');
    },

    async modify(payload) {
        return requestAI('/ai/process', {
            ...payload,
            mode: 'modify',
            overwrite: false,
        }, 'Modify request failed');
    },

    async agent(payload) {
        return requestAI('/ai/agent', {
            ...payload,
            max_steps: payload.max_steps ?? 4,
        }, 'Agent request failed');
    },

    async agentProgress(sessionId, requestId, signal) {
        const path = `/ai/agent/${encodeURIComponent(sessionId)}/progress?request_id=${encodeURIComponent(requestId)}`;
        const response = await fetch(`${BASE_URL}${path}`, { signal, cache: 'no-store' });
        if (response.status === 404) return null;
        if (!response.ok) throw new Error(`Progress unavailable (${response.status})`);
        return response.json();
    },

    async confirmOverwrite(payload) {
        return requestAI('/ai/process', {
            ...payload,
            mode: 'modify',
            overwrite: true,
        }, 'Overwrite request failed');
    },

    async listFunctions(format = 'openai') {
        return requestAIFunctions(format);
    },

    async invokeFunction(name, args = {}) {
        return requestAI('/ai/functions/invoke', {
            name,
            arguments: args,
        }, 'AI function invocation failed');
    },

    async listConversations() {
        return requestAIGet('/ai/conversations', 'Failed to list AI conversations');
    },

    async archiveConversation(payload) {
        return requestAI('/ai/conversations', payload, 'Failed to archive AI conversation');
    },

    async getConversation(archiveId) {
        return requestAIGet(`/ai/conversations/${encodeURIComponent(archiveId)}`, 'Failed to load AI conversation');
    },

    async updateConversation(archiveId, details) {
        return requestAI(`/ai/conversations/${encodeURIComponent(archiveId)}`, details, 'Failed to update conversation', 'PATCH');
    },

    async pinConversation(archiveId, pinned) {
        return requestAI(`/ai/conversations/${encodeURIComponent(archiveId)}/pin`, { pinned }, 'Failed to pin conversation', 'PATCH');
    },

    async exportConversation(archiveId) {
        return requestAIGet(`/ai/conversations/${encodeURIComponent(archiveId)}/export`, 'Failed to export conversation');
    },

    async importConversation(bundle) {
        return requestAI('/ai/conversations/import', bundle, 'Failed to import conversation');
    },

    async branchConversation(archiveId, payload = {}) {
        return requestAI(`/ai/conversations/${encodeURIComponent(archiveId)}/branch`, payload, 'Failed to branch conversation');
    },

    async restoreConversation(archiveId, sessionId = null) {
        return requestAI(
            `/ai/conversations/${encodeURIComponent(archiveId)}/restore`,
            sessionId ? { session_id: sessionId } : {},
            'Failed to restore AI conversation'
        );
    },

    async deleteConversation(archiveId) {
        return requestAIDelete(
            `/ai/conversations/${encodeURIComponent(archiveId)}`,
            'Failed to delete AI conversation'
        );
    },

    async clearConversations() {
        return requestAIDelete('/ai/conversations', 'Failed to clear AI conversations');
    },
};
