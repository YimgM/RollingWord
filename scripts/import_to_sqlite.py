#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据迁移与更新工具：将 data.json 同步到 SQLite 数据库的 words 表
"""

import json
import os
import sys

# 将 backend 目录加入环境变量，以便引用数据库模块
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.database import get_db, init_db

DATA_JSON_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data/data.json')

def json_to_string(obj):
    """辅助函数：处理原 JSON 中某些字段可能是列表或字典的情况"""
    # 只有当数据严格为 None 或本就是空字符串时，才返回 ""
    if obj is None or obj == "":
        return ""
    if isinstance(obj, str):
        return obj
    return json.dumps(obj, ensure_ascii=False)

def import_data():
    if not os.path.exists(DATA_JSON_PATH):
        print(f"未找到数据文件: {DATA_JSON_PATH}")
        return

    with open(DATA_JSON_PATH, 'r', encoding='utf-8') as f:
        words_data = json.load(f)

    # 确保表结构存在
    init_db()

    query = '''
        INSERT INTO words (
            word, definition_cn, definition_en, cognates, 
            synonyms_antonyms, sentences, notes, confusables, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(word) DO UPDATE SET
            definition_cn = excluded.definition_cn,
            definition_en = excluded.definition_en,
            cognates = excluded.cognates,
            synonyms_antonyms = excluded.synonyms_antonyms,
            sentences = excluded.sentences,
            notes = excluded.notes,
            confusables = excluded.confusables,
            updated_at = CURRENT_TIMESTAMP
    '''

    count_inserted_or_updated = 0
    with get_db() as db:
        for item in words_data:
            word = item.get('word')
            if not word:
                continue
            
            db.execute(query, (
                word,
                json_to_string(item.get('definition_cn')),
                json_to_string(item.get('definition_en')),
                json_to_string(item.get('cognates')),
                json_to_string(item.get('synonyms_antonyms')),
                json_to_string(item.get('sentences')),
                json_to_string(item.get('notes')),
                json_to_string(item.get('confusables'))
            ))
            count_inserted_or_updated += 1

    print(f"数据迁移完毕。共处理 {count_inserted_or_updated} 个单词。")

if __name__ == '__main__':
    import_data()