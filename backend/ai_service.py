#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 服务模块：负责与外部大语言模型交互
"""

import json
import os
import anthropic

# 隔离模型配置
API_KEY = os.environ.get("ANTHROPIC_AUTH_TOKEN", "3a5dd3389848406081554e2e7dac32e1.U7zPLjzeeAfvXEBI")
BASE_URL = os.environ.get("ANTHROPIC_BASE_URL", "https://open.bigmodel.cn/api/anthropic")
MODEL_NAME = os.environ.get("ANTHROPIC_MODEL", "glm-5")

# 懒加载初始化客户端
_client = None

def _get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=API_KEY, base_url=BASE_URL)
    return _client

def correct_word_data(word: str, user_feedback: str, current_data: dict) -> dict:
    """
    提交纠错反馈并返回修正后的 JSON 数据
    如果失败，抛出 ValueError 或 RuntimeError
    """
    prompt = f"""你是一个英语单词数据处理专家。用户发现单词数据有问题，请根据用户反馈修正数据。

单词：{word}

当前数据：
{json.dumps(current_data, ensure_ascii=False, indent=2)}

用户反馈：
{user_feedback}

原始笔记格式说明：
- 用户用 **word** 标记核心单词
- 中文释义紧跟在单词后面
- `_内容_` 或 `*内容*` 格式通常是助记提示词，内容应放入notes字段
- 同义词通常用"同"、"类"、"="等标记
- 例句是包含该单词的完整英文句子

请根据用户反馈修正数据，返回修正后的JSON对象：
{{"word": "...", "definition_cn": "...", "definition_en": "...", "cognates": [...], "notes": "...", "synonyms_antonyms": [...], "sentences": [...], "confusables": [...] }}

修正规则：
1. 必须严格保留“当前数据”中的所有字段（包括 cognates, confusables 等）。
2. 必须严格保持原有的数据类型（原本是列表 [] 的必须返回列表，原本是字符串 "" 的返回字符串，原本包含字典对象的原样保留内部结构）。
3. 仅根据用户反馈修改对应字段的文本内容。
4. 只返回合法的 JSON 对象，不要输出任何额外的 markdown 标记、解释或说明。
"""
    try:
        client = _get_client()
        message = client.messages.create(
            model=MODEL_NAME,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )
        response_text = message.content[0].text.strip()
        
        # 清洗可能存在的 Markdown 代码块包裹
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1].split('```')[0]

        start = response_text.find('{')
        end = response_text.rfind('}')
        if start == -1 or end == -1:
            raise ValueError("AI 返回内容未包含有效的 JSON 对象")
            
        return json.loads(response_text[start:end + 1])
        
    except json.JSONDecodeError as e:
        raise ValueError(f"AI 返回的 JSON 格式错误: {e}")
    except Exception as e:
        raise RuntimeError(f"AI 请求失败: {e}")