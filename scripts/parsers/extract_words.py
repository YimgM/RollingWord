#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
单词提取脚本 - 从Effie导出的Markdown笔记中提取单词信息
不依赖外部API，直接使用正则表达式和文本解析
"""

import json
import re
from pathlib import Path

INPUT_FILE = "wordbank0.md"
OUTPUT_FILE = "data.json"


def read_markdown(filepath):
    """读取markdown文件"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def extract_words(content):
    """从markdown内容中提取单词"""
    words = []
    lines = content.split('\n')

    # 跳过的章节
    skip_section = False

    for i, line in enumerate(lines):
        stripped = line.strip()

        # 检测章节标题
        if stripped.startswith('## '):
            skip_section = 'Terminology' in stripped
            continue

        if skip_section or not stripped:
            continue

        # 跳过标记行
        if any(x in stripped for x in ['⟷', '/ə/', '/ɪ/', '加粗ctrl', '标注Shift']):
            continue
        if re.match(r'^[秋夏][一二三四五六七八九十]+$', stripped):
            continue

        # 提取 **word** 格式的单词
        matches = list(re.finditer(r'\*\*([a-zA-Z\'\-]+)\*\*', line))

        for match in matches:
            word = match.group(1)
            if len(word) <= 1:
                continue

            # 获取该行的剩余内容作为释义
            rest_of_line = line[match.end():].strip()

            # 解析释义部分
            definition_cn = ""
            definition_en = ""
            synonyms = ""
            notes = ""

            # 清理开头的特殊标记
            rest_of_line = re.sub(r"^[,/\. \t]+", "", rest_of_line)

            # 尝试分离中文和英文释义
            # 中文通常在前，英文（如果有）可能在括号里或者用|分隔
            parts = rest_of_line.split('|')

            if len(parts) >= 2:
                definition_cn = parts[0].strip()
                definition_en = parts[1].strip()
            else:
                # 尝试提取中文释义
                cn_match = re.search(r'^([^\x00-\x7F]+)', rest_of_line)
                if cn_match:
                    definition_cn = cn_match.group(1)
                else:
                    definition_cn = rest_of_line[:50] if rest_of_line else ""

            # 提取同义词（包含同、|类、=等标记的内容）
            syn_match = re.search(r'(?:同|类|like|=)\s*\*{0,2}([a-zA-Z]+)\*{0,2}', line)
            if syn_match:
                synonyms = syn_match.group(1)

            # 提取记忆内容（包含_记忆_的内容）
            note_match = re.search(r'_([^_]+)_', line)
            if note_match:
                notes = note_match.group(1)

            # 查找例句（前后行中的英文句子）
            sentences = find_sentences(lines, i, word)

            word_data = {
                "word": word,
                "definition_cn": definition_cn,
                "definition_en": definition_en,
                "synonyms_antonyms": synonyms,
                "sentences": sentences,
                "notes": notes
            }

            words.append(word_data)

    return words


def find_sentences(lines, current_idx, word):
    """查找包含该单词的例句"""
    sentences = []

    # 向前向后查找3行
    for j in range(max(0, current_idx - 3), min(len(lines), current_idx + 4)):
        line = lines[j].strip()
        if not line:
            continue

        # 检查是否是英文句子（包含多个英文单词）
        if len(re.findall(r'[a-zA-Z]+', line)) >= 5:
            # 检查是否包含目标单词
            if re.search(r'\b' + re.escape(word) + r'\b', line, re.IGNORECASE):
                # 清理句子
                sentence = re.sub(r'\*\*', '', line)
                if len(sentence) > 20 and sentence not in sentences:
                    sentences.append(sentence)

    return '; '.join(sentences[:2])  # 最多返回2个例句


def merge_duplicates(words):
    """合并重复单词"""
    word_dict = {}

    for item in words:
        word_key = item['word'].lower()

        if word_key not in word_dict:
            word_dict[word_key] = item.copy()
        else:
            existing = word_dict[word_key]
            # 合并非空字段
            for key in ['definition_cn', 'definition_en', 'synonyms_antonyms', 'sentences', 'notes']:
                new_val = item.get(key, '').strip()
                if new_val and not existing.get(key):
                    existing[key] = new_val
                elif new_val and existing.get(key) and new_val not in existing[key]:
                    if key == 'sentences':
                        existing[key] = existing[key] + '; ' + new_val
                    elif key not in ['sentences'] and len(new_val) > len(existing[key]):
                        existing[key] = new_val

    return list(word_dict.values())


def clean_definition(text):
    """清理释义文本"""
    if not text:
        return ""

    # 移除markdown标记
    text = re.sub(r'\*\*', '', text)
    text = re.sub(r'\*', '', text)
    text = re.sub(r'_', '', text)

    # 移除多余的空格
    text = ' '.join(text.split())

    # 截断过长的文本
    if len(text) > 200:
        text = text[:250] + '...'

    return text.strip()


def main():
    print(f"正在读取文件: {INPUT_FILE}")
    content = read_markdown(INPUT_FILE)
    print(f"文件大小: {len(content)} 字符")

    print("正在提取单词...")
    words = extract_words(content)
    print(f"初步提取: {len(words)} 个单词")

    print("正在合并重复...")
    merged = merge_duplicates(words)
    print(f"合并后: {len(merged)} 个单词")

    # 清理数据
    print("正在清理数据...")
    for w in merged:
        w['definition_cn'] = clean_definition(w.get('definition_cn', ''))
        w['definition_en'] = clean_definition(w.get('definition_en', ''))
        w['synonyms_antonyms'] = clean_definition(w.get('synonyms_antonyms', ''))
        w['sentences'] = clean_definition(w.get('sentences', ''))
        w['notes'] = clean_definition(w.get('notes', ''))

    # 移除完全空释义的单词
    merged = [w for w in merged if w['definition_cn'] or w['definition_en'] or w['notes']]
    print(f"最终: {len(merged)} 个单词")

    print(f"正在保存到 {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2, separators=(',', ': '))
        f.write('\n')

    print("完成！")

    # 显示一些示例
    print("\n示例数据:")
    for w in merged[:3]:
        print(f"  {w['word']}: {w['definition_cn'][:30]}...")


if __name__ == "__main__":
    main()
