#!/usr/bin/env python3
"""
生成形近词(confusables)数据。
对 data.json 中每个词，检查前后±5位置的词，
用编辑距离+公共前缀判断相似度，排除已有cognates，
将形近词写入 confusables 字段。
"""

import json
import re


def edit_distance(a, b):
    """计算编辑距离"""
    m, n = len(a), len(b)
    dp = list(range(n + 1))
    for i in range(1, m + 1):
        prev = dp[0]
        dp[0] = i
        for j in range(1, n + 1):
            temp = dp[j]
            if a[i-1] == b[j-1]:
                dp[j] = prev
            else:
                dp[j] = 1 + min(prev, dp[j], dp[j-1])
            prev = temp
    return dp[n]


def common_prefix_len(a, b):
    """公共前缀长度"""
    i = 0
    while i < len(a) and i < len(b) and a[i] == b[i]:
        i += 1
    return i


def is_similar(word_a, word_b):
    """判断两个词是否形近"""
    a, b = word_a.lower(), word_b.lower()

    # 太短的词跳过（3字母以下容易误判）
    if len(a) <= 3 or len(b) <= 3:
        return False

    # 长度差太大不算形近
    if abs(len(a) - len(b)) > 4:
        return False

    # 编辑距离
    dist = edit_distance(a, b)
    max_len = max(len(a), len(b))
    similarity = 1 - dist / max_len

    # 公共前缀占比
    prefix = common_prefix_len(a, b)
    prefix_ratio = prefix / min(len(a), len(b))

    # 判定条件：编辑距离相似度 >= 0.6 且 公共前缀 >= 3
    return similarity >= 0.6 and prefix >= 3


def get_cognate_words(entry):
    """获取一个词条的所有cognate词"""
    cognates = entry.get('cognates', [])
    if isinstance(cognates, list):
        return {c['word'].lower() for c in cognates if isinstance(c, dict) and 'word' in c}
    return set()


def main():
    with open('data.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    total = len(data)
    added_count = 0
    window = 5  # 前后各查5个

    for i, entry in enumerate(data):
        word = entry['word']
        cognate_words = get_cognate_words(entry)
        confusables = []

        # 检查前后±window范围内的词
        start = max(0, i - window)
        end = min(total, i + window + 1)

        for j in range(start, end):
            if j == i:
                continue
            other = data[j]
            other_word = other['word']

            # 排除同源词
            if other_word.lower() in cognate_words:
                continue

            # 也排除对方cognates中包含当前词的情况
            other_cognates = get_cognate_words(other)
            if word.lower() in other_cognates:
                continue

            if is_similar(word, other_word):
                confusables.append({
                    'word': other_word,
                    'definition_cn': other.get('definition_cn', '')
                })

        entry['confusables'] = confusables
        if confusables:
            added_count += 1
            print(f"  {word} <-> {', '.join(c['word'] for c in confusables)}")

    print(f"\n共 {total} 个词，{added_count} 个词有形近词")

    with open('data.json', 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, separators=(',', ': '))
        f.write('\n')

    print("已写入 data.json")


if __name__ == '__main__':
    main()
