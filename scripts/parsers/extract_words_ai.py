#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RollingWord - AI智能单词提取脚本
使用AI理解笔记语义，结构化提取单词数据
"""

import json
import os
import re
import sys
import anthropic

INPUT_FILE = "wordbank0.md"
OUTPUT_FILE = "data.json"
PROMPT_FILE = "prompt.md"

# 每块包含的行数（避免超出context）
CHUNK_SIZE = 60

# 从 Claude Code 的 settings.json 读取配置
def load_claude_settings():
    settings_path = os.path.expanduser(r"~\.claude\settings.json")
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        env = settings.get("env", {})
        return {
            "api_key": env.get("ANTHROPIC_AUTH_TOKEN", ""),
            "base_url": env.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            "model": env.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        }
    except Exception as e:
        print(f"警告：无法读取 settings.json: {e}")
        return {
            "api_key": os.environ.get("ANTHROPIC_AUTH_TOKEN", ""),
            "base_url": os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
            "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6"),
        }

_cfg = load_claude_settings()

client = anthropic.Anthropic(
    api_key=_cfg["api_key"],
    base_url=_cfg["base_url"],
)
MODEL = _cfg["model"]


def load_system_prompt():
    """从prompt.md中提取系统提示词"""
    with open(PROMPT_FILE, 'r', encoding='utf-8') as f:
        content = f.read()

    # 提取第一个```代码块作为系统提示词
    match = re.search(r'## 系统提示词.*?```\n(.*?)```', content, re.DOTALL)
    if match:
        return match.group(1).strip()

    raise ValueError("prompt.md 中未找到系统提示词")


def preprocess_markdown(filepath):
    """读取并预处理markdown，去掉完全无用的行"""
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    cleaned = []
    for line in lines:
        s = line.strip()
        # 跳过：键盘符号说明行、纯日期章节行、空行保留用于分块
        if re.match(r'^⟷.*加粗ctrl', s):
            continue
        if re.match(r'^[秋夏][一二三四五六七八九十]+$', s):
            continue
        cleaned.append(line)

    return ''.join(cleaned)


def split_into_chunks(content, chunk_size=CHUNK_SIZE):
    """按自然断点分块，每块约chunk_size行"""
    lines = content.split('\n')
    chunks = []
    current = []
    word_count = 0

    for line in lines:
        current.append(line)
        # 统计本行有多少加粗单词（粗略估算条目数）
        word_count += len(re.findall(r'\*\*[a-zA-Z]', line))

        # 到达阈值且当前行是空行（自然断点），切块
        if word_count >= chunk_size and line.strip() == '':
            chunks.append('\n'.join(current))
            current = []
            word_count = 0

    if current:
        chunks.append('\n'.join(current))

    return chunks


def call_ai(system_prompt, chunk_content):
    """调用AI解析一个chunk"""
    user_message = f"请解析以下英语学习笔记，提取所有单词信息：\n\n---\n{chunk_content}\n---"

    response = client.messages.create(
        model=MODEL,
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}]
    )

    text = response.content[0].text.strip()

    # 提取JSON
    if '```json' in text:
        text = text.split('```json')[1].split('```')[0]
    elif '```' in text:
        text = text.split('```')[1].split('```')[0]

    # 确保从[开始
    start = text.find('[')
    end = text.rfind(']')
    if start != -1 and end != -1:
        text = text[start:end + 1]

    return json.loads(text)


def merge_duplicates(words):
    """合并重复单词，保留信息更丰富的版本"""
    seen = {}
    for item in words:
        key = item['word'].lower()
        if key not in seen:
            seen[key] = item
        else:
            # 合并：对每个字段，保留更长/更丰富的那个
            existing = seen[key]
            for field in ['definition_cn', 'definition_en', 'cognates',
                          'synonyms_antonyms', 'sentences', 'notes']:
                new_val = item.get(field, '').strip()
                old_val = existing.get(field, '').strip()
                if new_val and not old_val:
                    existing[field] = new_val
                elif new_val and old_val and new_val not in old_val:
                    if field == 'sentences':
                        existing[field] = old_val + '；' + new_val
                    elif len(new_val) > len(old_val):
                        existing[field] = new_val

    return list(seen.values())


def validate_word(item):
    """验证单词条目是否有效"""
    word = item.get('word', '').strip()
    if not word or len(word) < 2:
        return False
    if not re.match(r'^[a-zA-Z\'\-\s]+$', word):
        return False
    # 至少有一个非空字段
    fields = ['definition_cn', 'definition_en', 'cognates', 'synonyms_antonyms', 'sentences', 'notes']
    return any(item.get(f, '').strip() for f in fields)


def ensure_fields(item):
    """确保所有字段存在"""
    defaults = {
        'word': '',
        'definition_cn': '',
        'definition_en': '',
        'cognates': '',
        'synonyms_antonyms': '',
        'sentences': '',
        'notes': ''
    }
    for k, v in defaults.items():
        if k not in item:
            item[k] = v
    return item


def main():
    print("=" * 50)
    print("RollingWord AI 单词提取器")
    print("=" * 50)

    # 加载系统提示词
    print(f"\n加载提示词: {PROMPT_FILE}")
    system_prompt = load_system_prompt()
    print(f"提示词长度: {len(system_prompt)} 字符")

    # 读取并预处理笔记
    print(f"\n读取笔记: {INPUT_FILE}")
    content = preprocess_markdown(INPUT_FILE)
    print(f"笔记大小: {len(content)} 字符")

    # 分块
    chunks = split_into_chunks(content, CHUNK_SIZE)
    print(f"分为 {len(chunks)} 块处理\n")

    all_words = []
    errors = []

    for i, chunk in enumerate(chunks):
        # 跳过没有单词的块
        if not re.search(r'\*\*[a-zA-Z]', chunk):
            continue

        word_count_in_chunk = len(re.findall(r'\*\*[a-zA-Z]', chunk))
        print(f"[{i+1}/{len(chunks)}] 处理第 {i+1} 块（约 {word_count_in_chunk} 个词）...", end=' ', flush=True)

        try:
            words = call_ai(system_prompt, chunk)
            valid_words = [ensure_fields(w) for w in words if validate_word(w)]
            all_words.extend(valid_words)
            print(f"✓ 提取 {len(valid_words)} 个单词")
        except json.JSONDecodeError as e:
            print(f"✗ JSON解析失败: {e}")
            errors.append(i + 1)
        except Exception as e:
            print(f"✗ 错误: {e}")
            errors.append(i + 1)

    print(f"\n初步提取: {len(all_words)} 个单词")

    # 合并重复
    merged = merge_duplicates(all_words)
    print(f"合并去重后: {len(merged)} 个单词")

    # 保存
    with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2, separators=(',', ': '))
        f.write('\n')

    print(f"\n已保存到 {OUTPUT_FILE}")

    if errors:
        print(f"\n以下块处理失败，可重新运行: {errors}")

    # 预览
    print("\n--- 前3条预览 ---")
    for w in merged[:3]:
        print(f"\n{w['word']}:")
        for k, v in w.items():
            if k != 'word' and v:
                print(f"  {k}: {v}")

    print("\n完成！")


if __name__ == "__main__":
    main()
