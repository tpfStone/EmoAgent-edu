import json

from app.config import Settings
from app.schemas.scenario import (
    EmotionIntensity,
    ScenarioAnalyzeRequest,
    ScenarioAnalyzeResponse,
    ScenarioLabel,
    SupportMode,
)
from app.schemas.safety import SafetyAction, SafetyGateResponse
from app.services.llm_client import LLMClientProtocol
from app.services.safety_gate_service import RED_REFERRAL_MESSAGE, YELLOW_REFERRAL_MESSAGE


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
        return f"""你是一个面向中国初中生情感教育系统的 F2 分析模块。你同时做三件事：
1. 作为第二道安全哨兵，复核 F1 本地安全门可能漏掉的明显自伤/自杀风险。
2. 如果没有明显风险，判断用户倾诉属于哪一类情境。
3. 判断这一轮更适合哪种支持路由，供后续生成模块调整语气。

【安全复核边界】
你不是主要安全门，不要过度推断；只有文本中出现明显风险证据时才判 yellow/red。
- green：普通焦虑、压力、难过、烦躁、失眠、被批评、被孤立、亲子冲突，但没有自伤/自杀意念、方法、时间或准备。
- yellow：出现被动死亡意念或模糊自伤/自杀表达，但没有具体方法、时间、准备行为。例如“不想活了”“想消失”“不想醒来”“活着没意思但没计划”。
- red：出现具体自伤/自杀方法、时间、地点、准备行为、已经实施或即将实施。例如“今晚吃药”“准备好了刀”“现在要跳下去”“写好遗书”。
如果安全复核为 red，系统会直接转介，不进入生成器；yellow 会作为非阻断支持状态保留并继续生成；但你仍需尽量给出 scenario，方便日志分析。

候选情境（四选一）：
- 学业压力：与考试、成绩、作业、学习状态、升学等相关。
- 同伴关系：与同学、朋友之间的相处、冲突、孤立、误会等相关。
- 亲子摩擦：与父母/家人之间的矛盾、不被理解、管控、沟通问题等相关。
- 其他：以上都不明显，或涉及多类难以归为单一类。

情境判断原则：
1. 结合历史综合判断，以当前消息为主。
2. 若同时涉及多类，选最主要的那一类；若确实无法区分主次，归"其他"。
3. 只输出 JSON，不要劝导或建议。

支持路由判断：
- emotion_first：用户明显处在较强的委屈、焦虑、羞耻、愤怒、崩溃、害怕、孤独等消极情绪里，当前主要是在倾诉或求被理解；即使没有说“怎么办”，也能看出情绪负荷很重。
- solution_seeking：用户明确在问“怎么办、怎么解决、怎么改变、怎么做、有什么办法、该不该”等，重点是想找到下一步，而不是只求被安慰。
- balanced：情绪和求助都有，或证据不足以明显偏向前两类。

情绪强度判断：
- low：轻微困扰、普通抱怨、信息不足。
- medium：明显难受、焦虑、烦躁、委屈，但仍能较清楚描述。
- high：强烈消极情绪、反复失控、强烈自责/恐惧/绝望感；但如果达到 yellow/red 风险，仍按安全复核转介。

help_seeking 只在用户明确寻求办法、改变、判断或下一步时为 true。不要把普通倾诉误判成求助。

输出严格 JSON：
{{
  "secondary_safety": {{
    "risk_level": "green/yellow/red",
    "matched_signals": ["命中的具体风险表达；green时为空数组"],
    "rationale": "一句话中文理由"
  }},
  "scenario": "学业压力/同伴关系/亲子摩擦/其他",
  "scenario_confidence": 0~1的小数,
  "support_mode": "emotion_first/solution_seeking/balanced",
  "emotion_intensity": "low/medium/high",
  "help_seeking": true/false,
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
        secondary_safety = self._parse_secondary_safety(data.get("secondary_safety"))
        support_mode = self._parse_support_mode(data.get("support_mode"))
        emotion_intensity = self._parse_emotion_intensity(
            data.get("emotion_intensity")
        )
        help_seeking = self._parse_bool(data.get("help_seeking", False))
        return self._response(
            scenario=scenario,  # type: ignore[arg-type]
            confidence=confidence,
            secondary_safety=secondary_safety,
            support_mode=support_mode,
            emotion_intensity=emotion_intensity,
            help_seeking=help_seeking,
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
            secondary_safety=self._safety_response(
                risk_level="yellow",
                matched_signals=["f2_fallback"],
                rationale="F2 调用失败，暂停生成以避免漏过潜在风险。",
            ),
            support_mode="balanced",
            emotion_intensity="medium",
            help_seeking=False,
            rationale=f"情境分类失败，默认归为其他：{reason}",
        )

    @staticmethod
    def _parse_support_mode(value) -> SupportMode:
        support_mode = str(value or "").strip()
        if support_mode in {"emotion_first", "solution_seeking", "balanced"}:
            return support_mode  # type: ignore[return-value]
        return "balanced"

    @staticmethod
    def _parse_emotion_intensity(value) -> EmotionIntensity:
        emotion_intensity = str(value or "").strip()
        if emotion_intensity in {"low", "medium", "high"}:
            return emotion_intensity  # type: ignore[return-value]
        return "medium"

    @staticmethod
    def _parse_bool(value) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n", ""}:
                return False
        return bool(value)

    def _parse_secondary_safety(self, raw_safety) -> SafetyGateResponse:
        if not isinstance(raw_safety, dict):
            return self._safety_response(
                risk_level="green",
                matched_signals=[],
                rationale="F2 响应未包含 secondary_safety，按 green 兼容处理。",
            )
        risk_level = str(raw_safety.get("risk_level", "")).strip()
        if risk_level not in {"green", "yellow", "red"}:
            risk_level = "green"
        matched_signals = raw_safety.get("matched_signals", [])
        if not isinstance(matched_signals, list):
            matched_signals = []
        rationale = str(raw_safety.get("rationale", "")).strip() or "F2 安全复核完成。"
        return self._safety_response(
            risk_level=risk_level,
            matched_signals=[str(signal) for signal in matched_signals],
            rationale=rationale,
        )

    @staticmethod
    def _safety_response(
        risk_level: str, matched_signals: list[str], rationale: str
    ) -> SafetyGateResponse:
        if risk_level == "green":
            action = SafetyAction(block_generation=False, referral_message="")
        elif risk_level == "yellow":
            action = SafetyAction(
                block_generation=False,
                referral_message=YELLOW_REFERRAL_MESSAGE,
            )
        else:
            action = SafetyAction(
                block_generation=True,
                referral_message=RED_REFERRAL_MESSAGE,
            )
        return SafetyGateResponse(
            risk_level=risk_level,
            matched_signals=matched_signals,
            rationale=rationale,
            action=action,
        )

    @staticmethod
    def _response(
        scenario: ScenarioLabel,
        confidence: float,
        secondary_safety: SafetyGateResponse,
        support_mode: SupportMode,
        emotion_intensity: EmotionIntensity,
        help_seeking: bool,
        rationale: str,
    ) -> ScenarioAnalyzeResponse:
        return ScenarioAnalyzeResponse(
            scenario=scenario,
            scenario_confidence=confidence,
            activated_casel=SCENARIO_CASEL_MAP[scenario],
            secondary_safety=secondary_safety,
            support_mode=support_mode,
            emotion_intensity=emotion_intensity,
            help_seeking=help_seeking,
            rationale=rationale,
        )
