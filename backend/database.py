#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据库连接与初始化管理
"""

import sqlite3
import os
from contextlib import contextmanager

# 数据库文件路径设为项目根目录下的 data 目录
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
DB_PATH = os.path.join(DATA_DIR, 'rollingword.db')

def dict_factory(cursor, row):
    """将 SQLite 的查询结果转换为字典，便于后续 JSON 序列化"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

@contextmanager
def get_db():
    """
    数据库连接上下文管理器，处理连接的创建、事务提交/回滚及关闭。
    使用方法: with get_db() as db: ...
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    
    try:
        # 启用外键约束 (SQLite 默认关闭)
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def init_db():
    """初始化数据库表结构，使用 IF NOT EXISTS 保证幂等性"""
    with get_db() as db:
        cursor = db.cursor()
        
        # 1. 核心词库表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT UNIQUE NOT NULL,
                definition_cn TEXT,
                definition_en TEXT,
                cognates TEXT,
                synonyms_antonyms TEXT,
                sentences TEXT,
                notes TEXT,
                confusables TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. 用户状态表 (使用 word_id 作为外键，级联删除)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_word_states (
                word_id INTEGER PRIMARY KEY,
                is_mastered BOOLEAN DEFAULT 0,
                is_unfamiliar BOOLEAN DEFAULT 0,
                is_important BOOLEAN DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
            )
        ''')
        
        # 3. 学习行为流表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS study_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL,
                action_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
            )
        ''')
        
        # 4. 纠错日志表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS correction_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word_id INTEGER NOT NULL,
                user_feedback TEXT,
                old_data TEXT,
                new_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (word_id) REFERENCES words(id) ON DELETE CASCADE
            )
        ''')
        
        # 5. 用户偏好表 (K-V 存储前端 UI 状态)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_preferences (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

def verify_db_exists():
    """
    验证数据库是否已正确生成且包含核心数据表。
    """
    if not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        # 如果文件为空，直接删除这个无效的残留文件，防止后续产生冲突
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        raise FileNotFoundError("未找到有效的数据库文件。")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='words'")
        if not cursor.fetchone():
            conn.close()
            raise RuntimeError("数据库结构不完整，缺失 word 表。")
        conn.close()
    except sqlite3.Error as e:
        raise RuntimeError(f"数据库文件损坏或无法读取: {e}")

if __name__ == '__main__':
    init_db()
    print(f"数据库初始化完成: {DB_PATH}")