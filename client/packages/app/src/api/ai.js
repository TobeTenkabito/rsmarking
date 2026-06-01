import { API_CONFIG } from './config.js';

const BASE_URL = API_CONFIG.aiGatewayUrl;

async function requestAI(path, payload, fallbackMessage) {
    try {
        const response = await fetch(`${BASE_URL}${path}`, {
            method: 'POST',
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
};
