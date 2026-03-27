/**
 * UI 视图层：专注 DOM 渲染与动画
 */
export class UIManager {
    constructor() {
        this.elements = {
            wordText: document.getElementById('wordText'),
            progressText: document.getElementById('progressText'),
            toast: document.getElementById('toast'),
            card: document.getElementById('wordCard'),
            actions: document.querySelector('.actions'),
            historyList: document.getElementById('historyListInCard') // 需在HTML中预置或动态生成
        };
    }

    showToast(message, type = '') {
        const { toast } = this.elements;
        toast.textContent = message;
        toast.className = `toast show ${type}`;
        setTimeout(() => toast.classList.remove('show'), 3000);
    }

    renderWord(word, isCorrected) {
        if (!word) {
            this._renderEmptyState();
            return;
        }

        const wordDisplay = document.querySelector('.word-display');
        this.elements.wordText.style.display = '';
        wordDisplay.style.borderBottom = '';

        const emptyState = wordDisplay.querySelector('.empty-state');
        if (emptyState) emptyState.style.display = 'none';

        this.elements.wordText.textContent = word.word;
        
        // 渲染各项释义
        this._renderInfoItem('definitionCn', word.definition_cn);
        this._renderInfoItem('definitionEn', word.definition_en);
        this._renderInfoItem('cognates', word.cognates);
        this._renderInfoItem('synonyms', word.synonyms_antonyms);
        this._renderInfoItem('sentences', word.sentences);
        this._renderInfoItem('confusables', word.confusables);
        this._renderInfoItem('notes', word.notes);

        // 更新按钮与标志
        this._updateActionButtons(word);
        
        document.getElementById('correctBtn').style.display = 'block';
        const rollbackBtn = document.getElementById('btnRollback');
        if (rollbackBtn) rollbackBtn.style.display = isCorrected ? 'block' : 'none';

        this.speakWord(word.word);
    }

    _renderInfoItem(id, content) {
        const el = document.getElementById(id);
        const span = el.querySelector('.content');
        let text = '';

        if (Array.isArray(content) && content.length > 0) {
            if (id === 'synonyms') {
                // 处理同反义词对象数组
                text = content.map(s => `${s.type === 'antonym' ? '反' : '同'} ${s.word}`).join('\n');
            } else if (id === 'cognates' || id === 'confusables') {
                // 处理同源/形近词对象数组
                text = content.map(c => `${c.word} ${c.definition_cn ? ' ' + c.definition_cn : ''}`.trim()).join('\n');
            } else if (typeof content[0] === 'string') {
                // 处理例句等纯字符串数组
                text = content.join('\n');
            }
        } else if (typeof content === 'string') {
            text = content;
        }

        if (text.trim()) {
            span.textContent = text;
            el.classList.add('visible');
        } else {
            el.classList.remove('visible');
        }
    }

    _updateActionButtons(word) {
        document.getElementById('btnMastered').classList.toggle('done', word.is_mastered);
        document.getElementById('btnUnfamiliar').classList.toggle('flagged', word.is_unfamiliar);
        document.getElementById('btnImportant').classList.toggle('marked', word.is_important);
    }

    _renderEmptyState() {
        const wordDisplay = document.querySelector('.word-display');
        this.elements.wordText.style.display = 'none'; // 隐藏 span
        wordDisplay.style.borderBottom = 'none';

        // 创建或复用独立的 empty-state 容器
        let emptyState = wordDisplay.querySelector('.empty-state');
        if (!emptyState) {
            emptyState = document.createElement('div');
            emptyState.className = 'empty-state';
            wordDisplay.appendChild(emptyState);
        }
        emptyState.style.display = 'block';
        emptyState.innerHTML = `
            <div class="icon">📚</div>
            <p>当前分类暂无单词</p>
            <p style="font-size: 0.85rem; margin-top: 8px; opacity: 0.7;">切换到其他分类继续学习</p>
        `;
        
        ['definitionCn', 'definitionEn', 'cognates', 'synonyms', 'sentences', 'confusables', 'notes']
            .forEach(id => document.getElementById(id).classList.remove('visible'));
        
        document.getElementById('correctBtn').style.display = 'none';
        const rollbackBtn = document.getElementById('btnRollback');
        if (rollbackBtn) rollbackBtn.style.display = 'none';
    }

    _formatTime(isoString) {
        const date = new Date(isoString);
        const diff = new Date() - date;
        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
        return date.toLocaleDateString();
    }

    renderHistoryList(historyData, allWords) {
        // 获取卡片的 DOM，用历史记录列表覆盖它
        const infoSection = document.getElementById('infoSection');
        const wordDisplay = document.querySelector('.word-display');
        
        // 隐藏常规播放器组件
        wordDisplay.style.display = 'none';
        infoSection.style.display = 'none';

        // 在历史界面隐藏纠错和撤销按钮
        document.getElementById('correctBtn').style.display = 'none';
        const rollbackBtn = document.getElementById('btnRollback');
        if (rollbackBtn) rollbackBtn.style.display = 'none';
        
        // 如果不存在 history 容器则动态创建一个
        let historyContainer = document.getElementById('historyListInCard');
        if (!historyContainer) {
            historyContainer = document.createElement('div');
            historyContainer.id = 'historyListInCard';
            historyContainer.className = 'history-list';
            this.elements.card.insertBefore(historyContainer, document.getElementById('correctBtn'));
        }
        historyContainer.style.display = 'flex';

        if (historyData.length === 0) {
            historyContainer.innerHTML = '<div class="history-empty">暂无学习记录</div>';
            return;
        }

        // 渲染列表
        historyContainer.innerHTML = historyData.map(h => {
            const wordData = allWords.find(w => w.id === h.id);
            if (!wordData) return ''; 
            const def = (wordData.definition_cn || '').substring(0, 50);
            return `
                <div class="history-item" data-id="${h.id}">
                    <div class="word">${wordData.word}</div>
                    <div class="definition">${def}</div>
                    <div class="time">${this._formatTime(h.time)}</div>
                </div>
            `;
        }).join('');
    }

    resetCardLayout() {
        document.querySelector('.word-display').style.display = 'block';
        document.getElementById('infoSection').style.display = 'flex';
        const historyContainer = document.getElementById('historyListInCard');
        if (historyContainer) historyContainer.style.display = 'none';
    }

    updateProgress(current, total) {
        this.elements.progressText.textContent = `${current} / ${total}`;
    }

    updateStats(words) {
        document.getElementById('statTotal').textContent = words.length;
        document.getElementById('statMastered').textContent = words.filter(w => w.is_mastered).length;
        document.getElementById('statImportant').textContent = words.filter(w => w.is_important).length;
    }

    switchTab(folder) {
        document.querySelectorAll('.tab').forEach(tab => {
            tab.classList.toggle('active', tab.dataset.folder === folder);
        });
        
        if (folder === 'history') {
            this.elements.actions.style.display = 'none';
            // 历史记录渲染逻辑移交 Controller (main.js)
        } else {
            this.elements.actions.style.display = 'grid';
        }
    }

    speakWord(word) {
        if ('speechSynthesis' in window) {
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(word);
            utterance.lang = 'en-US';
            utterance.rate = 0.9;
            window.speechSynthesis.speak(utterance);
        }
    }

    openCorrectModal(currentDataStr) {
        document.getElementById('previewData').textContent = currentDataStr;
        document.getElementById('feedbackText').value = '';
        document.getElementById('correctModal').classList.add('show');
    }

    closeCorrectModal() {
        document.getElementById('correctModal').classList.remove('show');
    }

    openRollbackModal(oldDataStr) {
        document.getElementById('rollbackPreviewData').textContent = oldDataStr;
        document.getElementById('rollbackModal').classList.add('show');
    }

    closeRollbackModal() {
        document.getElementById('rollbackModal').classList.remove('show');
    }
}