const BASE_URL = 'http://localhost:8006';

export const AIAPI = {

    /**
     * 分析模式：发送空间数据分析请求
     * @param {Object} payload - { target_id, data_type, language, user_prompt }
     * @returns {Promise<{status, mode, report, file_url}>}
     */
    async analyze(payload) {
        try {
            const response = await fetch(`${BASE_URL}/ai/process`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...payload,
                    mode: 'analyze',
                    overwrite: false
                })
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `分析请求失败 (${response.status})`);
            }
            return await response.json();
        } catch (error) {
            console.error('[AIAPI] analyze Error:', error);
            throw error;
        }
    },

    /**
     * 修改模式：发送结构化数据修改请求
     * @param {Object} payload - { target_id, data_type, language, user_prompt }
     * @returns {Promise<{status, mode, action, modified_data, new_index_id?, new_layer_id?}>}
     */
    async modify(payload) {
        try {
            const response = await fetch(`${BASE_URL}/ai/process`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...payload,
                    mode: 'modify',
                    overwrite: false   // 默认新建，覆盖由 confirmOverwrite() 单独触发
                })
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `修改请求失败 (${response.status})`);
            }
            return await response.json();
        } catch (error) {
            console.error('[AIAPI] modify Error:', error);
            throw error;
        }
    },

    /**
     * 覆盖确认：用户手动确认后调用，将 overwrite 置为 true
     * @param {Object} payload - 与 modify() 相同的 payload
     * @returns {Promise<{status, mode, action, modified_data}>}
     */
    async confirmOverwrite(payload) {
        try {
            const response = await fetch(`${BASE_URL}/ai/process`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    ...payload,
                    mode: 'modify',
                    overwrite: true    // 用户已确认，执行覆盖
                })
            });
            if (!response.ok) {
                const err = await response.json().catch(() => ({}));
                throw new Error(err.detail || `覆盖请求失败 (${response.status})`);
            }
            return await response.json();
        } catch (error) {
            console.error('[AIAPI] confirmOverwrite Error:', error);
            throw error;
        }
    }
};
