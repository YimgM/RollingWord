/**
 * API 网络层：封装后端 HTTP 接口调用
 */
class ApiClient {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl;
    }

    async _request(endpoint, options = {}) {
        const url = `${this.baseUrl}${endpoint}`;
        const defaultHeaders = { 'Content-Type': 'application/json' };
        
        const config = {
            ...options,
            headers: { ...defaultHeaders, ...options.headers }
        };

        try {
            const response = await fetch(url, config);
            const result = await response.json();

            if (!response.ok || !result.success) {
                throw new Error(result.error || `HTTP Error: ${response.status}`);
            }
            return result.data;
        } catch (error) {
            console.error(`[API Error] ${endpoint}:`, error.message);
            throw error;
        }
    }

    // 获取全量单词和状态
    getProgress() {
        return this._request('/api/progress', { method: 'GET' });
    }

    // 获取存在纠错记录的单词列表
    getCorrectedWords() {
        return this._request('/api/corrected_words', { method: 'GET' });
    }

    // 更新单词的单一状态 (如 is_mastered: 1)
    markWord(wordId, stateField, value) {
        return this._request('/api/action/mark', {
            method: 'POST',
            body: JSON.stringify({ word_id: wordId, state_field: stateField, value: value ? 1 : 0 })
        });
    }

    // 同步 UI 偏好 (如 last_folder)
    syncUiState(stateDict) {
        return this._request('/api/action/ui_state', {
            method: 'POST',
            body: JSON.stringify(stateDict)
        });
    }

    // 提交 AI 纠错
    submitCorrection(wordId, feedback) {
        return this._request('/api/correct', {
            method: 'POST',
            body: JSON.stringify({ word_id: wordId, user_feedback: feedback })
        });
    }

    // 获取回滚预览数据
    previewRollback(wordId) {
        return this._request('/api/rollback_preview', {
            method: 'POST',
            body: JSON.stringify({ word_id: wordId })
        });
    }

    // 确认执行回滚
    executeRollback(wordId) {
        return this._request('/api/rollback', {
            method: 'POST',
            body: JSON.stringify({ word_id: wordId })
        });
    }
}

export const api = new ApiClient();