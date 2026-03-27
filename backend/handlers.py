#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
业务逻辑处理模块：负责参数校验、核心逻辑调用与标准响应封装
"""

import json
import queries
import ai_service
import database

def build_response(code: int, data=None, error: str = None) -> tuple:
    """
    构建标准化的 API 响应结构
    规范: {"success": bool, "data": any, "error": str|null}
    """
    resp = {"success": code < 400}
    if data is not None:
        resp["data"] = data
    if error is not None:
        resp["error"] = error
    return code, resp

def handle_get_progress() -> tuple:
    """获取全量词库与用户学习进度"""
    try:
        words = queries.get_all_words_with_states()
        return build_response(200, data={"words": words})
    except Exception as e:
        return build_response(500, error=f"数据库查询失败: {e}")

def handle_get_corrected_words() -> tuple:
    """获取存在纠错记录的单词文本列表"""
    try:
        words = queries.get_corrected_words_list()
        return build_response(200, data=words)
    except Exception as e:
        return build_response(500, error=f"查询纠错列表失败: {e}")

def handle_action_mark(payload: dict) -> tuple:
    """更新单词单一学习状态"""
    word_id = payload.get('word_id')
    state_field = payload.get('state_field')
    value = payload.get('value')

    if word_id is None or state_field is None or value is None:
        return build_response(400, error="缺少必要参数: word_id, state_field, value")

    try:
        # 开启单一事务，包含状态更新与日志记录
        with database.get_db() as db:
            queries.update_word_state(db, word_id, state_field, bool(value))
            
            action_map = {
                'is_mastered': 'mark_mastered' if value else 'unmark_mastered',
                'is_unfamiliar': 'mark_unfamiliar' if value else 'unmark_unfamiliar',
                'is_important': 'mark_important' if value else 'unmark_important'
            }
            queries.add_study_history(db, word_id, action_map.get(state_field, 'unknown_action'))
            
        return build_response(200, data={"message": "状态已更新"})
    except ValueError as e:
        return build_response(400, error=str(e))
    except Exception as e:
        return build_response(500, error=f"状态更新失败: {e}")

def handle_action_ui_state(payload: dict) -> tuple:
    """持久化前端 UI 状态"""
    allowed_keys = {'last_folder'}
    
    try:
        with database.get_db() as db:
            for key, value in payload.items():
                if key in allowed_keys:
                    queries.upsert_user_pref(db, key, str(value))
        return build_response(200, data={"message": "UI 状态已同步"})
    except Exception as e:
        return build_response(500, error=f"偏好保存失败: {e}")

def handle_ai_correct(payload: dict) -> tuple:
    """处理 AI 纠错请求"""
    word_id = payload.get('word_id')
    user_feedback = payload.get('user_feedback')

    if not word_id or not user_feedback:
        return build_response(400, error="缺少必要参数: word_id 或 user_feedback")

    try:
        current_data = queries.get_word_by_id(word_id)
        if not current_data:
            return build_response(404, error="未找到指定的单词")

        # 构建纯净的载荷喂给 AI，剔除数据库内部字段和用户状态
        clean_data = {
            k: v for k, v in current_data.items() 
            if k not in ['id', 'is_mastered', 'is_unfamiliar', 'is_important', 'last_updated', 'created_at', 'updated_at']
        }

        # 调用外部 AI 服务
        word_text = clean_data.get('word', '')
        corrected_data = ai_service.correct_word_data(word_text, user_feedback, clean_data)

        # 事务性写入日志与更新源数据
        with database.get_db() as db:
            queries.log_correction(db, word_id, user_feedback, current_data, corrected_data)
            queries.update_word_definitions(db, word_id, corrected_data)

        return build_response(200, data={
            "old_data": current_data, 
            "new_data": corrected_data
        })
    except ValueError as e:
        return build_response(400, error=str(e))
    except Exception as e:
        return build_response(500, error=str(e))

def handle_rollback_preview(payload: dict) -> tuple:
    """获取指定单词的纠错回滚预览"""
    word_text = payload.get('word_id')
    if not word_text:
        return build_response(400, error="缺少参数: word_id")

    try:
        with database.get_db() as db:
            log = queries.get_latest_correction_log(db, word_id)
        if not log:
            return build_response(404, error="未找到该单词的纠错历史")
            
        old_data = json.loads(log['old_data'])
        return build_response(200, data={"old_data": old_data})
    except Exception as e:
        return build_response(500, error=str(e))

def handle_rollback(payload: dict) -> tuple:
    """执行纠错历史回滚"""
    word_text = payload.get('word_id')
    if not word_text:
        return build_response(400, error="缺少参数: word_id")

    try:
        with database.get_db() as db:
            log = queries.get_latest_correction_log(db, word_id)
            if not log:
                return build_response(404, error="未找到回滚目标")

            log_id = log['id']
            old_data = json.loads(log['old_data'])

            queries.update_word_definitions(db, word_id, old_data)
            queries.delete_correction_log(db, log_id)

        return build_response(200, data={
            "message": "恢复成功", 
            "restored_data": old_data
        })
    except Exception as e:
        return build_response(500, error=str(e))