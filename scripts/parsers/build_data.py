#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
直接从markdown笔记解析单词，生成data.json
无需外部API，基于prompt.md中确定的规则用正则实现
"""

import json
import re

INPUT_FILE = "wordbank0.md"
OUTPUT_FILE = "data.json"

def parse_notes(line):
    """提取 _..._ 格式的助记内容，去掉'记忆'两字"""
    notes = []
    for m in re.finditer(r'_([^_]+)_', line):
        content = m.group(1).strip()
        content = re.sub(r'^记忆[:：\s]*', '', content)
        content = re.sub(r'^记\s*', '', content)
        if content:
            notes.append(content)
    return '；'.join(notes)

def clean_markdown(text):
    """去掉**标记"""
    return re.sub(r'\*\*', '', text).strip()

def is_sentence_line(line):
    """判断是否是独立的例句行（非单词定义行）"""
    s = line.strip()
    # 以大写字母开头，包含多个英文单词，不含**
    if '**' in s:
        return False
    en_words = re.findall(r'[a-zA-Z]+', s)
    if len(en_words) >= 6 and re.match(r'^[A-Z]', s):
        return True
    return False

def extract_definition_cn(text):
    """从行文本中提取中文释义（去掉音标、词性以外的英文部分）"""
    # 保留音标（/.../ 格式）+ 词性 + 中文
    # 去掉**word**之后的其他**word**
    text = re.sub(r'\*\*[a-zA-Z][^\*]*\*\*', '', text)
    # 去掉纯英文单词（但保留音标）
    # 先把音标替换为占位符
    phonetics = re.findall(r'/[^/]+/', text)
    for i, p in enumerate(phonetics):
        text = text.replace(p, f'__PHONETIC{i}__', 1)
    # 去掉剩余的纯ASCII英文词（保留中文、标点、数字）
    text = re.sub(r'[a-zA-Z][a-zA-Z\'\-\.]*', '', text)
    # 恢复音标
    for i, p in enumerate(phonetics):
        text = text.replace(f'__PHONETIC{i}__', p)
    # 去掉多余标点和空格
    text = re.sub(r'[|/\\]+', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    text = text.strip('，。,.')
    return text

def parse_markdown(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    words = {}  # key: word.lower() -> dict

    skip_patterns = [
        r'^⟷.*加粗ctrl',
        r'^[秋夏][一二三四五六七八九十]+$',
        r'^题型',
        r'^[-\s⟷↑]+$',
        r'^##\s',
    ]

    def should_skip(line):
        s = line.strip()
        if not s:
            return True
        for p in skip_patterns:
            if re.match(p, s):
                return True
        return False

    def upsert(word, field, value):
        """更新单词字段，保留更长的值"""
        if not value:
            return
        key = word.lower()
        if key not in words:
            words[key] = {
                'word': word,
                'definition_cn': '',
                'definition_en': '',
                'cognates': '',
                'synonyms_antonyms': '',
                'sentences': '',
                'notes': ''
            }
        existing = words[key].get(field, '')
        if not existing:
            words[key][field] = value
        elif value not in existing:
            if field == 'sentences':
                words[key][field] = existing + '；' + value
            elif field in ('cognates', 'notes', 'synonyms_antonyms'):
                words[key][field] = existing + '；' + value
            elif len(value) > len(existing):
                words[key][field] = value

    i = 0
    total_lines = len(lines)

    while i < total_lines:
        line = lines[i].rstrip('\n')
        i += 1

        if should_skip(line):
            continue

        # 查找本行所有加粗单词
        bold_words = re.findall(r'\*\*([a-zA-Z][a-zA-Z\s\'\-]*)\*\*', line)
        if not bold_words:
            # 没有加粗词但是例句行，暂存（后面关联）
            continue

        # 第一个加粗词是核心词
        core_word = bold_words[0].strip()
        if len(core_word) < 2:
            continue

        # ---- 提取各字段 ----

        # 1. 音标
        phonetic = ''
        ph_match = re.search(r'/([^/\s]{1,10})/', line)
        if ph_match:
            phonetic = '/' + ph_match.group(1) + '/'

        # 2. 从核心词后面的文本提取释义
        # 找到核心词在行中的位置
        core_pattern = r'\*\*' + re.escape(core_word) + r'\*\*'
        cm = re.search(core_pattern, line)
        if not cm:
            continue
        after_core = line[cm.end():]

        # 2a. 先去掉notes部分
        after_no_notes = re.sub(r'_[^_]+_', '', after_core)

        # 2b. 去掉其他加粗词及其后内容（cognates处理）
        # 找到下一个**之前的内容作为释义区域
        def_area = re.split(r'\*\*', after_no_notes)[0]

        # 2c. 提取英文释义（如 flourish, entirely 等直接给出的英文释义）
        # 规则：如果释义区域开头是英文单词，且后面有中文，则该英文是英文释义
        def_area_stripped = def_area.strip().lstrip('/').strip()
        # 去掉音标
        def_area_stripped = re.sub(r'^/[^/]*/\s*', '', def_area_stripped)
        # 去掉词性标注开头
        def_area_stripped = re.sub(r'^(vt\.|vi\.|n\.|adj\.|adv\.|v\.)\s*', '', def_area_stripped)

        en_def = ''
        cn_def = ''

        # 判断：如果定义区域以英文字母开头，且紧跟中文
        en_start = re.match(r'^([a-zA-Z][a-zA-Z\s,]+?)\s+(?=[^\x00-\x7F])', def_area_stripped)
        if en_start:
            en_word_candidate = en_start.group(1).strip()
            # 只取单个英文词或简单词组（不超过3个词）
            if len(en_word_candidate.split()) <= 3 and len(en_word_candidate) < 30:
                en_def = en_word_candidate
                cn_part = def_area_stripped[en_start.end():]
            else:
                cn_part = def_area_stripped
        else:
            cn_part = def_area_stripped

        # 提取中文部分
        cn_chars = re.findall(r'[\u4e00-\u9fff，。、；：""''【】（）\[\]n\.vt\.vi\.adj\.adv\.v\.C\[\]\s\d/\-,\.]+', cn_part)
        if cn_chars:
            cn_def = ''.join(cn_chars).strip().strip('，。；')
        else:
            # 如果没有中文，整个def_area作为释义
            cn_def = def_area.strip()

        # 拼上音标
        if phonetic:
            cn_def = phonetic + ' ' + cn_def if cn_def else phonetic
        cn_def = cn_def.strip()

        # 3. 同源词/衍生词（同行其他加粗词 + 未加粗的相关词）
        cognate_parts = []
        # 其他加粗词
        for w in bold_words[1:]:
            w = w.strip()
            if len(w) < 2:
                continue
            # 找该词后的释义
            wp = r'\*\*' + re.escape(w) + r'\*\*'
            wm = re.search(wp, line)
            if wm:
                wafter = line[wm.end():]
                wafter = re.sub(r'_[^_]+_', '', wafter)
                wafter = re.split(r'\*\*', wafter)[0].strip()
                # 去掉同义词标记
                wafter = re.sub(r'^[|同类=⟷\s]+', '', wafter).strip()
                if wafter:
                    cognate_parts.append(f'{w} {wafter}')
                else:
                    cognate_parts.append(w)

        # 同行未加粗的英文词（排除介词、冠词等）
        # 去掉已处理的内容，找剩余英文词
        line_no_bold = re.sub(r'\*\*[^\*]+\*\*', '', line)
        line_no_notes = re.sub(r'_[^_]+_', '', line_no_bold)
        # 找形如 "word释义" 或 "word adj./n." 的模式
        loose_cognates = re.findall(r'\b([A-Z][a-z]+(?:tion|ment|ness|ity|ous|ive|ary|ory|ize|ise|ate|ful|less|ly))\b', line_no_notes)
        for lc in loose_cognates:
            if lc.lower() != core_word.lower() and lc not in [b.strip() for b in bold_words]:
                cognate_parts.append(lc)

        cognates_str = '；'.join(cognate_parts) if cognate_parts else ''

        # 4. 近反义词
        syn_parts = []
        # 同/|类/= 后面的词
        for m in re.finditer(r'(?:同|类|=|同理)\s*\*{0,2}([a-zA-Z][a-zA-Z\s\'\-]+)\*{0,2}', line):
            syn_parts.append(m.group(1).strip())
        # ⟷ 后面的词
        for m in re.finditer(r'[⟷↔]\s*\*{0,2}([a-zA-Z][a-zA-Z\s\'\-]+)\*{0,2}', line):
            syn_parts.append('⟷' + m.group(1).strip())
        synonyms_str = '；'.join(syn_parts) if syn_parts else ''

        # 5. 例句：本行中包含核心词的英文短语/句子
        # 去掉markdown标记
        clean_line = re.sub(r'\*\*[^\*]+\*\*', lambda m: m.group(0).replace('**', ''), line)
        clean_line = re.sub(r'\*\*', '', clean_line)
        clean_line = re.sub(r'_[^_]+_', '', clean_line)
        # 找包含核心词的英文片段
        sentence = ''
        word_pattern = re.compile(r'\b' + re.escape(core_word) + r'\b', re.IGNORECASE)
        if word_pattern.search(clean_line):
            # 提取英文句子片段（连续英文+标点）
            en_segments = re.findall(r'[A-Za-z][^。！？\n]{10,}', clean_line)
            for seg in en_segments:
                if word_pattern.search(seg):
                    sentence = seg.strip()
                    break

        # 6. 助记
        notes = parse_notes(line)

        # 写入
        upsert(core_word, 'definition_cn', cn_def)
        if en_def:
            upsert(core_word, 'definition_en', en_def)
        if cognates_str:
            upsert(core_word, 'cognates', cognates_str)
        if synonyms_str:
            upsert(core_word, 'synonyms_antonyms', synonyms_str)
        if sentence:
            upsert(core_word, 'sentences', sentence)
        if notes:
            upsert(core_word, 'notes', notes)

        # 查看后续行是否有独立例句
        for j in range(i, min(i + 3, total_lines)):
            next_line = lines[j].strip()
            if not next_line:
                break
            if is_sentence_line(next_line) and word_pattern.search(next_line):
                upsert(core_word, 'sentences', clean_markdown(next_line))

    result = list(words.values())
    # 过滤掉没有任何实质内容的条目
    result = [w for w in result if any(w.get(f) for f in ['definition_cn', 'definition_en', 'notes'])]
    return result


def main():
    print(f"读取 {INPUT_FILE}...")
    data = parse_markdown(INPUT_FILE)
    print(f"提取到 {len(data)} 个单词")

    with open(OUTPUT_FILE, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(data, f, ensure_ascii=False, indent=2, separators=(',', ': '))
        f.write('\n')
    print(f"已写入 {OUTPUT_FILE}")

    print("\n--- 前5条预览 ---")
    for w in data[:5]:
        print(f"\n{w['word']}:")
        for k, v in w.items():
            if k != 'word' and v:
                print(f"  {k}: {v[:60]}")


if __name__ == '__main__':
    main()
