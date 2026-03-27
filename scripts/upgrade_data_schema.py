#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据向上归一化脚本：将老旧的字符串拼接格式，
升级为标准的结构化 JSON 对象/数组格式，并生成变更报告。
"""

import json
import os
import re
import copy

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_JSON_PATH = os.path.join(BASE_DIR, 'data/data.json')
NEW_DATA_JSON_PATH = os.path.join(BASE_DIR, 'data/new_data.json')
REPORT_PATH = os.path.join(BASE_DIR, 'data/upgrade_report.txt')

def upgrade_synonyms(data):
    if not data: return []
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        return data
    
    result = []
    items = [data] if isinstance(data, str) else data
    for item in items:
        if not isinstance(item, str): continue
        parts = re.split(r'[;；]', item)
        for part in parts:
            part = part.strip()
            if not part: continue
            
            t = "antonym" if part.startswith("反") or "⟷" in part else "synonym"
            word = re.sub(r'^[同类=反⟷\s]+', '', part).strip()
            if word:
                result.append({"type": t, "word": word})
    return result

def upgrade_cognates(data):
    if not data: return []
    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        return data
        
    result = []
    items = [data] if isinstance(data, str) else data
    
    POS_PATTERN = r'^(n\.|v\.|vi\.|vt\.|adj\.|adv\.|prep\.|conj\.|pron\.)'
    CHINESE_PATTERN = r'^[\u4e00-\u9fa5]'
    
    for item in items:
        if not isinstance(item, str): continue
        parts = re.split(r'[;；]', item)
        
        current_word = None
        current_def = ""
        
        for part in parts:
            part = part.strip()
            if not part: continue
            
            # 判断当前这段是否是上一个单词释义的延续
            is_continuation = False
            if current_word:
                if re.match(POS_PATTERN, part) or re.match(CHINESE_PATTERN, part):
                    is_continuation = True
            
            if is_continuation:
                current_def += "；" + part
            else:
                # 结算上一个单词
                if current_word is not None:
                    result.append({"word": current_word, "definition_cn": current_def.strip()})
                
                # 提取新单词：寻找单词与释义的边界（首个中文、词性、或音标）
                # 注意：此处用 search 寻找边界位置
                boundary_match = re.search(r'([\u4e00-\u9fa5]|n\.|v\.|vi\.|vt\.|adj\.|adv\.|prep\.|conj\.|pron\.|/|\[|\()', part)
                
                if boundary_match:
                    idx = boundary_match.start()
                    w = part[:idx].strip()
                    d = part[idx:].strip()
                    if w:
                        current_word = w
                        current_def = d
                    else:
                        # 极端边界情况：开头就是词性但之前没有current_word
                        current_word = part
                        current_def = ""
                else:
                    # 纯英文无释义（如 "infringe on", "brochure"）
                    current_word = part
                    current_def = ""
        
        # 结算本 item 的最后一个单词
        if current_word is not None:
            result.append({"word": current_word, "definition_cn": current_def.strip()})
            
    return result

def upgrade_sentences(data):
    if not data: return []
    if isinstance(data, str):
        return [s.strip() for s in re.split(r'[;；]', data) if s.strip()]
    
    result = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.strip():
                result.append(item.strip())
            elif isinstance(item, dict):
                text = item.get('sentence') or item.get('text') or ''
                if text.strip(): result.append(text.strip())
    return result

def is_changed(old_val, new_val):
    """简单对比升级前后的值是否发生了实质性变化"""
    if old_val == new_val:
        return False
    # 如果原本是空字符串/None，升级后变成了空列表 []，视为未发生实质变化
    if not old_val and new_val == []:
        return False
    return True

def main():
    if not os.path.exists(DATA_JSON_PATH):
        print(f"未找到 {DATA_JSON_PATH}")
        return

    with open(DATA_JSON_PATH, 'r', encoding='utf-8') as f:
        words = json.load(f)

    print(f"开始结构化升级 {len(words)} 个单词...")

    change_logs = []
    changed_count = 0

    for word_obj in words:
        original = copy.deepcopy(word_obj)
        word_text = word_obj.get('word', 'UNKNOWN')
        
        # 执行升级
        word_obj['synonyms_antonyms'] = upgrade_synonyms(word_obj.get('synonyms_antonyms'))
        word_obj['cognates'] = upgrade_cognates(word_obj.get('cognates'))
        word_obj['confusables'] = upgrade_cognates(word_obj.get('confusables'))
        word_obj['sentences'] = upgrade_sentences(word_obj.get('sentences'))

        # 对比变更
        word_changes = []
        for field in ['synonyms_antonyms', 'cognates', 'confusables', 'sentences']:
            if is_changed(original.get(field), word_obj.get(field)):
                word_changes.append({
                    "field": field,
                    "old": original.get(field),
                    "new": word_obj.get(field)
                })
        
        if word_changes:
            changed_count += 1
            log_entry = f"单词: {word_text}\n"
            for change in word_changes:
                log_entry += f"  [{change['field']}]\n"
                log_entry += f"    - 旧数据: {json.dumps(change['old'], ensure_ascii=False)}\n"
                log_entry += f"    + 新数据: {json.dumps(change['new'], ensure_ascii=False)}\n"
            change_logs.append(log_entry)

    # 写入 JSON 数据
    with open(NEW_DATA_JSON_PATH, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(words, f, ensure_ascii=False, indent=2)

    # 写入报告
    with open(REPORT_PATH, 'w', encoding='utf-8', newline='\n') as f:
        f.write(f"数据升级报告\n")
        f.write(f"共检测到 {changed_count} 个单词发生了结构化转换。\n")
        f.write("=" * 60 + "\n\n")
        f.write("\n---\n".join(change_logs))

    print(f"升级完成。已转换 {changed_count} 条记录。")
    print(f"详细变更对照表已生成至: {REPORT_PATH}")

if __name__ == '__main__':
    main()