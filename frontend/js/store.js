import { api } from './api.js';

/**
 * Store 状态管理：负责维护本地内存数据和队列调度
 */
export class WordStore {
    constructor() {
        this.words = [];             // 核心词库及状态 (来自后端)
        this.correctedWords = new Set(); // 有纠错记录的单词文本
        
        this.currentFolder = 'all';
        this.queue = [];             // 当前文件夹的播放队列 (存引用)
        this.currentIndex = 0;       // 队列指针
        
        // 浏览历史仅作 UI 便捷功能，保存在本地即可
        this.localHistory = JSON.parse(localStorage.getItem('rollingword_history') || '[]');
    }

    async init() {
        const [progressData, correctedData] = await Promise.all([
            api.getProgress(),
            api.getCorrectedWords()
        ]);
        
        this.words = progressData.words;
        this.correctedWords = new Set(correctedData);
        this._migrateLegacyStorage();
    }

    _migrateLegacyStorage() {
        // 迁移历史记录
        try {
            let history = JSON.parse(localStorage.getItem('rollingword_history') || '[]');
            if (history.length > 0 && history[0].word && !history[0].id) {
                console.log("检测到旧版历史记录，正在迁移至 ID 模式...");
                history = history.map(h => {
                    const wordObj = this.words.find(w => w.word.toLowerCase() === h.word.toLowerCase());
                    return wordObj ? { id: wordObj.id, time: h.time } : null;
                }).filter(Boolean);
                localStorage.setItem('rollingword_history', JSON.stringify(history));
            }
            this.localHistory = history;
        } catch (e) {
            this.localHistory = [];
            localStorage.removeItem('rollingword_history');
        }

        // 迁移播放队列缓存
        const folders = ['all', 'mastered', 'unfamiliar', 'important'];
        folders.forEach(folder => {
            try {
                const q = JSON.parse(localStorage.getItem(`q_${folder}`) || '[]');
                if (q.length > 0 && typeof q[0] === 'string') {
                    console.log(`检测到 ${folder} 的旧版队列，正在迁移至 ID 模式...`);
                    const migratedQ = q.map(wordText => {
                        const wordObj = this.words.find(w => w.word.toLowerCase() === wordText.toLowerCase());
                        return wordObj ? wordObj.id : null;
                    }).filter(Boolean);
                    localStorage.setItem(`q_${folder}`, JSON.stringify(migratedQ));
                }
            } catch (e) {
                localStorage.removeItem(`q_${folder}`);
            }
        });
    }

    get currentWord() {
        return this.queue[this.currentIndex] || null;
    }

    // 根据当前文件夹规则过滤单词
    _getValidWordsForFolder(folder) {
        switch (folder) {
            case 'mastered':   return this.words.filter(w => w.is_mastered);
            case 'unfamiliar': return this.words.filter(w => w.is_unfamiliar);
            case 'important':  return this.words.filter(w => w.is_important);
            case 'history':
                return this.localHistory
                    .map(h => this.words.find(w => w.id === h.id))
                    .filter(Boolean);
            default: // 'all'
                return this.words.filter(w => !w.is_mastered);
        }
    }

    // 生成或恢复播放队列
    buildQueue(folder, forceReshuffle = false) {
        this.currentFolder = folder;
        const validWords = this._getValidWordsForFolder(folder);
        
        if (validWords.length === 0) {
            this.queue = [];
            this.currentIndex = 0;
            return;
        }

        // 历史记录无需打乱
        if (folder === 'history') {
            this.queue = validWords;
            this.currentIndex = 0;
            return;
        }

        // 尝试从本地恢复该文件夹上次打乱的队列排序
        // 如果强制重排，直接忽略本地缓存
        const savedQueueIds = forceReshuffle ? [] : JSON.parse(localStorage.getItem(`q_${folder}`) || '[]');
        this.currentIndex = forceReshuffle ? 0 : parseInt(localStorage.getItem(`i_${folder}`) || '0');

        let activeQueue = [];
        if (savedQueueIds.length > 0) {
            // 恢复并清洗失效词
            activeQueue = savedQueueIds
                .map(id => validWords.find(w => w.id === id))
                .filter(Boolean);
                
            // 将新加入的词打乱后追加
            const newWords = validWords.filter(vw => !savedQueueIds.includes(vw.id));
            if (newWords.length > 0) {
                newWords.sort(() => Math.random() - 0.5);
                activeQueue.push(...newWords);
            }
        } else {
            // 生成新队列
            activeQueue = [...validWords].sort(() => Math.random() - 0.5);
            this.currentIndex = 0;
        }

        if (this.currentIndex >= activeQueue.length) this.currentIndex = 0;
        this.queue = activeQueue;
        this._persistQueueState();
    }

    _persistQueueState() {
        if (this.currentFolder === 'history') return;
        const queueIds = this.queue.map(w => w.id);
        localStorage.setItem(`q_${this.currentFolder}`, JSON.stringify(queueIds));
        localStorage.setItem(`i_${this.currentFolder}`, this.currentIndex.toString());
    }

    next() {
        if (this.queue.length === 0) return false;
        
        this.currentIndex++;
        
        // 队列循环重置
        if (this.currentIndex >= this.queue.length) {
            this.buildQueue(this.currentFolder, true); // 重洗
            return 'reshuffled'; 
        }
        
        this._persistQueueState();
        return true;
    }

    prev() {
        if (this.currentIndex > 0) {
            this.currentIndex--;
            this._persistQueueState();
        }
    }

    // 记录本地访问历史
    recordHistory(wordId) {
        this.localHistory = this.localHistory.filter(h => h.id !== wordId);
        this.localHistory.unshift({ id: wordId, time: new Date().toISOString() });
        if (this.localHistory.length > 100) this.localHistory.pop();
        localStorage.setItem('rollingword_history', JSON.stringify(this.localHistory));
    }

    // 乐观更新单词状态，并剔除无效队列项
    async updateWordState(wordId, field, value) {
        const word = this.words.find(w => w.id === wordId);
        if (!word) return;

        // 1. 内存乐观更新
        word[field] = value ? 1 : 0;
        
        // 互斥逻辑：熟记与不熟互斥
        if (field === 'is_mastered' && value) word.is_unfamiliar = 0;
        if (field === 'is_unfamiliar' && value) word.is_mastered = 0;

        // 2. 清洗当前队列（如果状态变更导致该词不再属于本文件夹）
        const validWords = this._getValidWordsForFolder(this.currentFolder);
        if (!validWords.some(w => w.id === wordId)) {
            const idx = this.queue.findIndex(w => w.id === wordId);
            if (idx > -1) {
                this.queue.splice(idx, 1);
                if (idx < this.currentIndex) this.currentIndex--; // 修正指针
                this._persistQueueState();
            }
        }

        // 3. 异步提交后端 (失败时抛出供 UI 层捕获)
        await api.markWord(wordId, field, value);
    }
}