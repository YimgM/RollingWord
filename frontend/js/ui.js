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
            leftSidebar: document.getElementById('leftSidebar'),
            navArrows: document.querySelector('.nav-arrows'),
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
        wordDisplay.style.display = 'block';

        const emptyState = wordDisplay.querySelector('.empty-state');
        if (emptyState) emptyState.style.display = 'none';

        this.elements.wordText.textContent = word.word;

        // 渲染各项释义（填充内容但保持折叠）
        this._renderInfoItem('definitionCn', word.definition_cn);
        this._renderInfoItem('definitionEn', word.definition_en);
        this._renderInfoItem('cognates', word.cognates);
        this._renderInfoItem('synonyms', word.synonyms_antonyms);
        this._renderInfoItem('sentences', word.sentences);
        this._renderInfoItem('confusables', word.confusables);
        this._renderInfoItem('notes', word.notes);

        // 更新按钮状态
        this._updateActionButtons(word);

        // 每次切换单词时重置为折叠状态
        this._setInfoCollapsed(true);

        // 显示查看按钮
        const viewToggleBtn = document.getElementById('viewToggleBtn');
        if (viewToggleBtn) viewToggleBtn.style.display = '';

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
                text = content.map(s => `${s.type === 'antonym' ? '反' : '同'} ${s.word}`).join('\n');
            } else if (id === 'cognates' || id === 'confusables') {
                text = content.map(c => `${c.word} ${c.definition_cn ? ' ' + c.definition_cn : ''}`.trim()).join('\n');
            } else if (typeof content[0] === 'string') {
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
        this.elements.wordText.style.display = 'none';
        wordDisplay.style.display = 'block';

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

        // 无词时隐藏查看按钮和详情区
        const viewToggleBtn = document.getElementById('viewToggleBtn');
        if (viewToggleBtn) viewToggleBtn.style.display = 'none';
        const infoSection = document.getElementById('infoSection');
        if (infoSection) infoSection.style.display = 'none';

        document.getElementById('correctBtn').style.display = 'none';
        const rollbackBtn = document.getElementById('btnRollback');
        if (rollbackBtn) rollbackBtn.style.display = 'none';
    }

    /**
     * 切换详情折叠/展开状态
     */
    toggleInfoSection() {
        const infoSection = document.getElementById('infoSection');
        const isCollapsed = infoSection.style.display === 'none' || infoSection.style.display === '';
        this._setInfoCollapsed(!isCollapsed);
    }

    _setInfoCollapsed(collapsed) {
        const infoSection = document.getElementById('infoSection');
        const btn = document.getElementById('viewToggleBtn');
        if (infoSection) infoSection.style.display = collapsed ? 'none' : 'flex';
        if (btn) btn.textContent = collapsed ? '查看释义' : '隐藏';
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
        const infoSection = document.getElementById('infoSection');
        const wordDisplay = document.querySelector('.word-display');

        wordDisplay.style.display = 'none';
        infoSection.style.display = 'none';

        const viewToggleBtn = document.getElementById('viewToggleBtn');
        if (viewToggleBtn) viewToggleBtn.style.display = 'none';

        document.getElementById('correctBtn').style.display = 'none';
        const rollbackBtn = document.getElementById('btnRollback');
        if (rollbackBtn) rollbackBtn.style.display = 'none';

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
        // 重置为折叠状态（不直接显示详情）
        this._setInfoCollapsed(true);
        const viewToggleBtn = document.getElementById('viewToggleBtn');
        if (viewToggleBtn) viewToggleBtn.style.display = '';
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

        const isHistory = folder === 'history';
        if (this.elements.leftSidebar) {
            this.elements.leftSidebar.style.display = isHistory ? 'none' : 'flex';
        }
        if (this.elements.navArrows) {
            this.elements.navArrows.style.display = isHistory ? 'none' : 'flex';
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
