#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库操作查询层封装
"""

from database import get_db
import json

def _parse_row(row: dict) -> dict:
    """将 SQLite 返回的行中的字符串反序列化为真实的 JSON 数组/对象，并强制类型约束"""
    if not row:
        return None
    res = dict(row)
    
    # 明确声明哪些字段必须是数组
    json_fields = ['cognates', 'synonyms_antonyms', 'sentences', 'confusables']
    
    for field in json_fields:
        val = res.get(field)
        if val and isinstance(val, str):
            try:
                res[field] = json.loads(val)
                # 如果反序列化出来不是列表（比如误存了对象），强制转为列表
                if not isinstance(res[field], list):
                    res[field] = [res[field]]
            except json.JSONDecodeError:
                res[field] = []
        else:
            # 如果数据库里是 None 或 ""，强制给一个空数组
            res[field] = []
            
    return res

def get_all_words_with_states():
    """获取全量词库及其对应的用户学习状态"""
    query = '''
        SELECT 
            w.id, w.word, w.definition_cn, w.definition_en, w.cognates, 
            w.synonyms_antonyms, w.sentences, w.notes, w.confusables,
            COALESCE(s.is_mastered, 0) as is_mastered,
            COALESCE(s.is_unfamiliar, 0) as is_unfamiliar,
            COALESCE(s.is_important, 0) as is_important
        FROM words w
        LEFT JOIN user_word_states s ON w.id = s.word_id
    '''
    with get_db() as db:
        cursor = db.execute(query)
        # 对每一行执行反序列化
        return [_parse_row(row) for row in cursor.fetchall()]

def update_word_state(db, word_id: int, state_field: str, value: bool):
    """
    更新单词的单一状态 (如: is_mastered, is_unfamiliar, is_important)
    采用 UPSERT (INSERT ... ON CONFLICT) 机制，若记录不存在则自动创建
    """
    valid_fields = {'is_mastered', 'is_unfamiliar', 'is_important'}
    if state_field not in valid_fields:
        raise ValueError(f"无效的状态字段: {state_field}")

    # 动态构造字段名是安全的，因为已通过白名单校验
    query = f'''
        INSERT INTO user_word_states (word_id, {state_field}, last_updated)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(word_id) DO UPDATE SET 
            {state_field} = excluded.{state_field},
            last_updated = CURRENT_TIMESTAMP
    '''
    db.execute(query, (word_id, int(value)))

def add_study_history(db, word_id: int, action_type: str):
    """记录用户操作行为，同时保留最近的 100 条记录机制"""
    db.execute(
        "INSERT INTO study_history (word_id, action_type) VALUES (?, ?)", 
        (word_id, action_type)
    )
    # 清理该单词/全局冗余历史记录 (视业务需求，此处保留全局最近 100 条)
    db.execute('''
        DELETE FROM study_history 
        WHERE id NOT IN (
            SELECT id FROM study_history ORDER BY created_at DESC LIMIT 100
        )
    ''')

def upsert_user_pref(db, key: str, value: str):
    """更新用户偏好配置（如最后停留的标签页）"""
    query = '''
        INSERT INTO user_preferences (key, value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(key) DO UPDATE SET 
            value = excluded.value,
            updated_at = CURRENT_TIMESTAMP
    '''
    db.execute(query, (key, value))

def get_user_pref(key: str, default: str = None):
    """获取用户偏好配置"""
    with get_db() as db:
        cursor = db.execute("SELECT value FROM user_preferences WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row['value'] if row else default

def get_word_by_id(word_id: int) -> dict:
    """根据 ID 获取单词详细信息"""
    with get_db() as db:
        cursor = db.execute("SELECT * FROM words WHERE id = ?", (word_id,))
        return _parse_row(cursor.fetchone())

def get_word_by_name(word_text: str) -> dict:
    """根据单词文本获取详细信息 (兼容旧版前端通过文本查询)"""
    with get_db() as db:
        cursor = db.execute("SELECT * FROM words WHERE word = ? COLLATE NOCASE", (word_text,))
        return _parse_row(cursor.fetchone())

def log_correction(db, word_id: int, feedback: str, old_data: dict, new_data: dict):
    """记录 AI 纠错日志"""
    db.execute('''
        INSERT INTO correction_logs (word_id, user_feedback, old_data, new_data)
        VALUES (?, ?, ?, ?)
    ''', (
        word_id, 
        feedback, 
        json.dumps(old_data, ensure_ascii=False), 
        json.dumps(new_data, ensure_ascii=False)
    ))

def update_word_definitions(db, word_id: int, new_data: dict):
    """更新单词的内容字段 (通常由 AI 纠错或回滚触发)"""
    
    def safe_json_dumps(val):
        """确保复杂数据结构被安全序列化为字符串以便入库"""
        if isinstance(val, (list, dict)):
            return json.dumps(val, ensure_ascii=False)
        # 如果是 None 则转为空字符串
        return val if val is not None else ""

    db.execute('''
        UPDATE words SET
            definition_cn = ?, definition_en = ?, cognates = ?,
            synonyms_antonyms = ?, sentences = ?, notes = ?,
            confusables = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    ''', (
        new_data.get('definition_cn', ''),
        new_data.get('definition_en', ''),
        safe_json_dumps(new_data.get('cognates')),
        safe_json_dumps(new_data.get('synonyms_antonyms')),
        safe_json_dumps(new_data.get('sentences')),
        new_data.get('notes', ''),
        safe_json_dumps(new_data.get('confusables')),
        word_id
    ))

def get_corrected_words_list() -> list:
    """获取存在纠错记录的单词文本列表"""
    with get_db() as db:
        cursor = db.execute('SELECT DISTINCT word_id FROM correction_logs')
        return [row['word_id'] for row in cursor.fetchall()]

def get_latest_correction_log(db, word_id: int) -> dict:
    """获取某个单词最新的一条纠错记录"""
    cursor = db.execute('''
        SELECT id, old_data, word_id 
        FROM correction_logs 
        WHERE word_id = ? 
        ORDER BY created_at DESC LIMIT 1
    ''', (word_id,))
    return cursor.fetchone()

def delete_correction_log(db, log_id: int):
    """删除指定的纠错日志"""
    db.execute("DELETE FROM correction_logs WHERE id = ?", (log_id,))