"""LLM Analyst — DeepSeek API 调用

使用 deepseek-v4-flash 模型，输入结构化 Evidence + Signals，
输出中文 Markdown + JSON。
"""

import json
import logging
from typing import Dict

import httpx

from athena.config import settings
from athena.llm.prompts import SYSTEM_PROMPT, build_research_prompt

logger = logging.getLogger(__name__)


class DeepSeekAnalyst:
    """DeepSeek LLM 研究分析师。

    只基于 Evidence 和 Signal 推理，不编造数据。
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
        base_url: str = "",
    ):
        self._api_key = api_key or settings.deepseek_api_key
        self._model = model or settings.deepseek_model
        self._base_url = base_url or settings.deepseek_base_url

        if not self._api_key:
            raise ValueError("DEEPSEEK_API_KEY 未配置，无法初始化 LLM Analyst")

        self._http = httpx.Client(timeout=httpx.Timeout(120.0))

    def analyze(
        self, symbol: str, evidence_list: list, signals: dict,
        ups_range=None, downs_range=None
    ) -> Dict:
        """执行研究分析。

        Args:
            symbol: 股票代码
            evidence_list: Evidence 字典列表
            signals: 信号字典（来自 compute_technical_signals）

        Returns:
            解析后的 JSON 输出
        """
        # 序列化为 JSON
        evidence_json = json.dumps(
            evidence_list, ensure_ascii=False, indent=2, default=str
        )
        signals_json = json.dumps(
            signals, ensure_ascii=False, indent=2, default=str
        )

        user_prompt = build_research_prompt(symbol, evidence_json, signals_json)

        # 调用 DeepSeek API
        response = self._http.post(
            f"{self._base_url}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self._model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 4096,
            },
        )

        response.raise_for_status()
        data = response.json()

        content = data["choices"][0]["message"]["content"]

        # 尝试解析 LLM 返回的 JSON
        return _parse_llm_response(content, symbol)

    def close(self):
        self._http.close()


def _parse_llm_response(content: str, symbol: str) -> Dict:
    """解析 LLM 返回的 JSON。

    LLM 可能返回 ```json ... ``` 包裹的 JSON，需要提取。
    """
    # 尝试直接解析
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 尝试提取 ```json ... ``` 块
    if "```json" in content:
        start = content.index("```json") + 7
        end = content.index("```", start)
        json_str = content[start:end].strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # 尝试提取第一个 { 到最后一个 }
    if "{" in content and "}" in content:
        start = content.index("{")
        end = content.rindex("}") + 1
        json_str = content[start:end]
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    # 解析失败，回退为原始内容
    logger.warning(f"LLM 返回无法解析为 JSON，使用原始文本")
    return {
        "symbol": symbol,
        "status": "Not Ready",
        "upside_probability_range": [0.0, 0.0],
        "downside_probability_range": [0.0, 0.0],
        "confidence": "Not Ready",
        "upside_path": [],
        "downside_risks": [],
        "key_evidence": [],
        "missing_evidence": ["LLM 输出无法解析"],
        "watchlist": [],
        "report_markdown": content,
    }
