import { api } from './api.js';
import { WordStore } from './store.js';
import { UIManager } from './ui.js';

class AppController {
    constructor() {
        this.store = new WordStore();
        this.ui = new UIManager();
    }

    async bootstrap() {
        try {
            await this.store.init();
            this.bindEvents();
            
            const lastFolder = localStorage.getItem('rollingword_last_folder') || 'all';
            await this.changeFolder(lastFolder);
            
            this.ui.updateStats(this.store.words);
        } catch (error) {
            this.ui.showToast('初始化失败: ' + error.message, 'error');
        }
    }

    async changeFolder(folder) {
        this.ui.switchTab(folder);
        localStorage.setItem('rollingword_last_folder', folder);
        api.syncUiState({ last_folder: folder }).catch(() => {});
        
        if (folder === 'history') {
            // 走独立的渲染管线
            this.ui.renderHistoryList(this.store.localHistory, this.store.words);
            this.ui.updateProgress(this.store.localHistory.length, this.store.words.length);
            
            // 绑定历史列表项的点击事件，跳转到 all 并定位
            document.querySelectorAll('.history-item').forEach(item => {
                item.addEventListener('click', () => {
                    const wordId = parseInt(item.dataset.id, 10);
                    this.changeFolder('all').then(() => {
                        let targetIdx = this.store.queue.findIndex(w => w.id === wordId);
                        if (targetIdx === -1) {
                            // 如果该词被 all 排除(如已熟记)，强制插入队首以便查看
                            const wordObj = this.store.words.find(w => w.id === wordId);
                            if (wordObj) this.store.queue.unshift(wordObj);
                            targetIdx = 0;
                        }
                        this.store.currentIndex = targetIdx;
                        this.showCurrentWord();
                    });
                });
            });
        } else {
            // 常规播放器管线
            this.ui.resetCardLayout();
            this.store.buildQueue(folder);
            this.showCurrentWord();
        }
    }

    showCurrentWord() {
        const word = this.store.currentWord;
        const isCorrected = word ? this.store.correctedWords.has(word.id) : false;
        
        this.ui.renderWord(word, isCorrected);
        this.ui.updateProgress(
            this.store.queue.length > 0 ? this.store.currentIndex + 1 : 0, 
            this.store.queue.length
        );

        if (word) this.store.recordHistory(word.id);
    }

    async handleStateToggle(field) {
        const word = this.store.currentWord;
        if (!word) return;

        const newValue = !word[field];
        
        // 乐观更新：先改内存，直接跳下一个单词
        try {
            await this.store.updateWordState(word.id, field, newValue);
            this.ui.updateStats(this.store.words); // 刷新统计数据
            
            if (field === 'is_mastered' || field === 'is_unfamiliar') {
                this.nextWord();
            } else {
                this.showCurrentWord(); // 仅刷新按钮 UI (如 Important)
            }
        } catch (error) {
            this.ui.showToast('同步失败，请检查网络', 'error');
            // 回滚内存状态 (可选)
        }
    }

    nextWord() {
        const result = this.store.next();
        if (result === 'reshuffled') this.ui.showToast('本组已完毕，开启新一轮重排', 'success');
        this.showCurrentWord();
    }

    async handleCorrectionSubmit() {
        const word = this.store.currentWord;
        const feedback = document.getElementById('feedbackText').value.trim();
        if (!word || !feedback) {
            this.ui.showToast('请输入纠错内容', 'error');
            return;
        }

        const btn = document.getElementById('submitCorrectBtn');
        btn.textContent = '处理中...';
        btn.disabled = true;

        try {
            const res = await api.submitCorrection(word.id, feedback);
            this.ui.showToast('纠错成功', 'success');
            
            // 更新内存词库与纠错记录集
            const wordIndex = this.store.words.findIndex(w => w.id === word.id);
            if (wordIndex > -1) this.store.words[wordIndex] = res.new_data;
            this.store.correctedWords.add(res.new_data.id);
            
            this.ui.closeCorrectModal();
            this.showCurrentWord(); // 刷新当前卡片
        } catch (error) {
            this.ui.showToast(error.message, 'error');
        } finally {
            btn.textContent = '提交纠错';
            btn.disabled = false;
        }
    }

    async previewRollback() {
        const word = this.store.currentWord;
        if (!word) return;

        const btn = document.getElementById('btnRollback');
        const originText = btn.textContent;
        btn.textContent = '获取中...';

        try {
            const res = await api.previewRollback(word.id);
            this.ui.openRollbackModal(JSON.stringify(res.old_data, null, 2));
        } catch (error) {
            this.ui.showToast(error.message, 'error');
        } finally {
            btn.textContent = originText;
        }
    }

    async executeRollback() {
        const word = this.store.currentWord;
        if (!word) return;

        const btn = document.getElementById('confirmRollbackBtn');
        btn.disabled = true;
        btn.textContent = '恢复中...';

        try {
            const res = await api.executeRollback(word.id);
            this.ui.showToast('恢复成功', 'success');

            // 更新内存
            const wordIndex = this.store.words.findIndex(w => w.id === word.id);
            if (wordIndex > -1) this.store.words[wordIndex] = res.restored_data;
            this.store.correctedWords.delete(word.id);

            this.ui.closeRollbackModal();
            this.showCurrentWord();
        } catch (error) {
            this.ui.showToast(error.message, 'error');
        } finally {
            btn.disabled = false;
            btn.textContent = '确认覆盖';
        }
    }

    bindEvents() {
        // 左侧标记按钮
        document.getElementById('btnMastered').addEventListener('click', () => this.handleStateToggle('is_mastered'));
        document.getElementById('btnUnfamiliar').addEventListener('click', () => this.handleStateToggle('is_unfamiliar'));
        document.getElementById('btnImportant').addEventListener('click', () => this.handleStateToggle('is_important'));

        // 导航箭头
        document.getElementById('btnNext').addEventListener('click', () => this.nextWord());
        document.getElementById('btnPrev')?.addEventListener('click', () => {
            this.store.prev();
            this.showCurrentWord();
        });

        // 查看/收起 切换
        document.getElementById('viewToggleBtn')?.addEventListener('click', () => this.ui.toggleInfoSection());

        // 右侧抽屉开关
        document.getElementById('listToggleBtn')?.addEventListener('click', () => {
            document.getElementById('rightPanel').classList.add('open');
            document.getElementById('panelBackdrop').classList.add('show');
        });
        document.getElementById('panelBackdrop')?.addEventListener('click', () => {
            document.getElementById('rightPanel').classList.remove('open');
            document.getElementById('panelBackdrop').classList.remove('show');
        });

        // 标签页切换（点击后关闭抽屉）
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                this.changeFolder(tab.dataset.folder);
                document.getElementById('rightPanel').classList.remove('open');
                document.getElementById('panelBackdrop').classList.remove('show');
            });
        });

        // 读音点击
        const wordTextEl = document.getElementById('wordText');
        if (wordTextEl) {
            wordTextEl.style.cursor = 'pointer';
            wordTextEl.addEventListener('click', () => {
                if (this.store.currentWord) this.ui.speakWord(this.store.currentWord.word);
            });
        }

        // 纠错弹窗事件绑定
        document.getElementById('correctBtn')?.addEventListener('click', () => {
            if (this.store.currentWord) {
                // 深拷贝并清洗内部系统字段，保持展示与提交给 AI 的数据纯净
                const cleanData = { ...this.store.currentWord };
                ['id', 'is_mastered', 'is_unfamiliar', 'is_important', 'last_updated', 'created_at', 'updated_at']
                    .forEach(k => delete cleanData[k]);
                
                this.ui.openCorrectModal(JSON.stringify(cleanData, null, 2));
            }
        });
        document.getElementById('closeCorrectModalBtn')?.addEventListener('click', () => this.ui.closeCorrectModal());
        document.getElementById('cancelCorrectBtn')?.addEventListener('click', () => this.ui.closeCorrectModal());
        document.getElementById('submitCorrectBtn')?.addEventListener('click', () => this.handleCorrectionSubmit());
        document.getElementById('correctModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'correctModal') this.ui.closeCorrectModal();
        });

        // 撤销回滚弹窗事件绑定
        document.getElementById('btnRollback')?.addEventListener('click', () => this.previewRollback());
        document.getElementById('closeRollbackModalBtn')?.addEventListener('click', () => this.ui.closeRollbackModal());
        document.getElementById('cancelRollbackBtn')?.addEventListener('click', () => this.ui.closeRollbackModal());
        document.getElementById('confirmRollbackBtn')?.addEventListener('click', () => this.executeRollback());
        document.getElementById('rollbackModal')?.addEventListener('click', (e) => {
            if (e.target.id === 'rollbackModal') this.ui.closeRollbackModal();
        });

        // 键盘快捷键 (排除输入框，拦截原生焦点)
        document.addEventListener('keydown', (e) => {
            if (['TEXTAREA', 'INPUT'].includes(e.target.tagName)) return;
            if (e.ctrlKey || e.metaKey || e.altKey) return;

            // 强制失焦，避免空格/回车误触已点击的按钮
            if (document.activeElement?.tagName === 'BUTTON') {
                document.activeElement.blur();
            }

            switch (e.key) {
                case 'ArrowRight':
                case ' ':
                    e.preventDefault();
                    this.nextWord();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    this.store.prev();
                    this.showCurrentWord();
                    break;
                case '1': 
                    this.handleStateToggle('is_mastered'); 
                    break;
                case '2': 
                    this.handleStateToggle('is_unfamiliar'); 
                    break;
                case '3': 
                    this.handleStateToggle('is_important'); 
                    break;
                case 'c':
                    if (this.store.currentWord) {
                        this.ui.openCorrectModal(JSON.stringify(this.store.currentWord, null, 2));
                    }
                    break;
                case 'z':
                    if (this.store.currentWord && this.store.correctedWords.has(this.store.currentWord.id)) {
                        this.previewRollback();
                    }
                    break;
                case 'Escape':
                    this.ui.closeCorrectModal();
                    this.ui.closeRollbackModal();
                    break;
            }
        });

        // 移动端防抖动滑动操作
        let touchStartX = 0;
        let touchStartY = 0;
        const wordCard = document.getElementById('wordCard');

        if (wordCard) {
            wordCard.addEventListener('touchstart', (e) => {
                touchStartX = e.changedTouches[0].screenX;
                touchStartY = e.changedTouches[0].screenY;
            }, { passive: true });

            wordCard.addEventListener('touchend', (e) => {
                const touchEndX = e.changedTouches[0].screenX;
                const touchEndY = e.changedTouches[0].screenY;
                
                const deltaX = touchEndX - touchStartX;
                const deltaY = touchEndY - touchStartY;

                // 仅在水平滑动距离大于 50px 且横向滑动幅度大于纵向时触发
                if (Math.abs(deltaX) > 50 && Math.abs(deltaX) > Math.abs(deltaY)) {
                    if (deltaX > 0) {
                        this.store.prev();
                        this.showCurrentWord();
                    } else {
                        this.nextWord();
                    }
                }
            }, { passive: true });
        }
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.appController = new AppController();
    window.appController.bootstrap();
});