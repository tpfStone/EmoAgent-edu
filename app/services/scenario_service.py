import json

from app.config import Settings
from app.schemas.scenario import (
    ScenarioAnalyzeRequest,
    ScenarioAnalyzeResponse,
    ScenarioLabel,
)
from app.services.llm_client import LLMClientProtocol


SCENARIO_CASEL_MAP: dict[ScenarioLabel, list[str]] = {
    "学业压力": ["自我觉察引导", "自我管理引导", "负责任决策引导"],
    "同伴关系": ["自我觉察引导", "社会觉察培养", "关系技能培养"],
    "亲子摩擦": ["自我觉察引导", "自我管理引导", "社会觉察培养", "关系技能培养"],
    "其他": ["自我觉察引导"],
}

VALID_SCENARIOS = set(SCENARIO_CASEL_MAP)


class ScenarioService:
    def __init__(self, llm_client: LLMClientProtocol, settings: Settings):
        self.llm_client = llm_client
        self.settings = settings

    async def analyze(self, request: ScenarioAnalyzeRequest) -> ScenarioAnalyzeResponse:
        try:
            raw_response = await self.llm_client.generate(
                prompt=self._build_prompt(request),
                timeout=self.settings.LLM_TIMEOUT,
                temperature=self.settings.SCENARIO_LLM_TEMPERATURE,
                max_tokens=self.settings.LLM_MAX_TOKENS,
            )
            return self._parse_response(raw_response)
        except Exception as exc:
            return self._fallback_response(str(exc))

    def _build_prompt(self, request: ScenarioAnalyzeRequest) -> str:
        window_size = self.settings.HISTORY_WINDOW_N * 2
        history = request.history[-window_size:]
        history_text = "\n".join(f"{item.role}: {item.text}" for item in history)
        return f"""你是一个面向中国初中生情感教育系统的情境分类模块。给定用户的倾诉和对话历史，判断这属于哪一类情境。你只分类，不回应、不评价。

候选情境（四选一）：
- 学业压力：与考试、成绩、作业、学习状态、升学等相关。
- 同伴关系：与同学、朋友之间的相处、冲突、孤立、误会等相关。
- 亲子摩擦：与父母/家人之间的矛盾、不被理解、管控、沟通问题等相关。
- 其他：以上都不明显，或涉及多类难以归为单一类。

判断原则：
1. 结合历史综合判断，以当前消息为主。
2. 若同时涉及多类，选最主要的那一类；若确实无法区分主次，归"其他"。
3. 只输出分类，不要劝导或建议。

输出严格 JSON：
{{
  "scenario": "学业压力/同伴关系/亲子摩擦/其他",
  "scenario_confidence": 0~1的小数,
  "rationale": "一句话中文理由"
}}

【对话历史】{history_text}
【当前消息】{request.current_message}
"""

    def _parse_response(self, raw_response: str) -> ScenarioAnalyzeResponse:
        data = json.loads(self._extract_json(raw_response))
        scenario = str(data.get("scenario", "")).strip()
        if scenario not in VALID_SCENARIOS:
            raise ValueError("invalid scenario")
        confidence = float(data.get("scenario_confidence", 0.0))
        confidence = min(max(confidence, 0.0), 1.0)
        rationale = str(data.get("rationale", "")).strip() or "已按文本内容判断情境。"
        return self._response(
            scenario=scenario,  # type: ignore[arg-type]
            confidence=confidence,
            rationale=rationale,
        )

    @staticmethod
    def _extract_json(raw_response: str) -> str:
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("no json object")
        return raw_response[start : end + 1]

    def _fallback_response(self, reason: str) -> ScenarioAnalyzeResponse:
        return self._response(
            scenario="其他",
            confidence=0.0,
            rationale=f"情境分类失败，默认归为其他：{reason}",
        )

    @staticmethod
    def _response(
        scenario: ScenarioLabel, confidence: float, rationale: str
    ) -> ScenarioAnalyzeResponse:
        return ScenarioAnalyzeResponse(
            scenario=scenario,
            scenario_confidence=confidence,
            activated_casel=SCENARIO_CASEL_MAP[scenario],
            rationale=rationale,
        )
