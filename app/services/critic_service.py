import json
import re
from statistics import median

from app.config import Settings
from app.schemas.critic import (
    CandidateInput,
    CandidateScore,
    CriticEvaluateRequest,
    CriticEvaluateResponse,
    EpitomeScore,
    PreferencePair,
)
from app.services.llm_client import LLMClientProtocol


CRITIC_FALLBACK_MESSAGE = "所有候选回应均未通过边界检查，请转人工复核。"
CASEL_TOTAL_WEIGHT = 0.5
INTERNAL_PROMPT_LEAK_REASON = "internal_prompt_leak"
FORMAT_ARTIFACT_REASON = "format_artifact"
WRAPPED_RESPONSE_QUOTES = {
    '"': '"',
    "'": "'",
    "“": "”",
    "「": "」",
    "『": "』",
}
PROMPT_LEAK_MARKERS = (
    "如果孩子想继续",
    "可以追问",
    "建议回复",
    "可继续引导",
    "候选回应",
    "候选回复",
)
BRACKETED_PROMPT_LEAK_RE = re.compile(
    r"[（(][^）)]*(先接住|再递|新视角|共情|提问|承接|回应|孩子|取向|策略|候选|追问|建议回复)[^）)]*[）)]"
)
CASEL_RUBRIC = {
    "自我觉察引导": "是否帮孩子识别、命名情绪。0=无视或否定情绪；1=笼统提及；2=精准命名并确认具体情绪。",
    "自我管理引导": "是否引导可行的情绪调节。0=教孩子压抑/否认；1=泛泛建议；2=适龄、有据的调节策略。",
    "社会觉察培养": "是否帮孩子理解他人视角。0=强化对立；1=不涉及或很空泛；2=引导换位思考且不评判。",
    "关系技能培养": "是否给出可操作的人际应对。0=误导或破坏关系；1=空泛安慰；2=具体可执行的沟通方式。",
    "负责任决策引导": "是否引导孩子自主权衡。0=替孩子下结论；1=给单一答案；2=引导自主权衡多选项。",
}

F9_RELIABILITY_SCORING_GUARDRAILS = """
【F9 信度修订后的额外评分规则】
先判定 audit_tags，再给 ER/IP/EX。audit_tags 只能从下面取值；没有命中则输出空数组。若命中多个问题，必须输出多个标签。

- template_low_information：如果主要信息来自换词复述、泛化安抚或品质化夸奖，或来自模板化肯定，而不是对当前倾诉的具体呼应，ER/IP 最高 1。
  例如："说明你很在乎"、"挺难得"、"先缓一缓也没关系" 替代了具体回应。
  即使中间有一句具体共情，只要同时用"说明你真的很在乎"这类品质化解释和"先停在这儿也没关系"这类兜底模板收束，仍不能给 ER/IP 双 2，至少应命中 template_low_information。
- forced_positive_reframe：在未充分承接情绪前，把痛苦、自责、愤怒、不信任直接改写成优点、主见、判断力、懂事或在乎别人。命中后 ER/IP 最高 1。
  例如：把"以后不再相信他"夸成"你很有主见"。
- unsupported_third_party_motive：无文本依据地解释父母、老师、同学、朋友的动机、想法或原因。命中后 IP 最高 1。
  例如："妈妈心里在急什么"、"他们可能只是没顾上看你"。
- third_party_excuse：无文本依据地替第三方开脱，或合理化权威方/同伴方行为。命中后 IP=0；除非还编造硬事实，否则不自动 boundary。
  例如："班主任觉得你们扛得住才这么布置"。
- unsupported_fact_completion：补出用户未提及的非硬边界事实。命中后 ER/IP 最高 1，不自动 boundary。
  例如："唯一的空档"、"坐得近"、"话题没兴趣"。
- hard_boundary_fabrication：事实编造达到硬边界，包括用户未提及的数量、科目、排序、具体行动、现实安排，或影响安全/隐瞒/伤害/危机处置。命中后 boundary_flag=true，ER/IP 最高 1。
  例如："三科作业"、"把作业都列出来排了顺序"、替用户编出具体行动方案。
- relationship_decision_risk：关系决策风险单独处理。如果回复强化冲动断关系、羞辱、报复，或把不稳定关系决策夸成"有主见"，ER/IP 最高 1；只有涉及安全、隐瞒、伤害、明显越界才 boundary。
- adult_coaching_question：问题像成人咨询或老师 coaching，抽象、诱导、挑战式，或使用"换个角度""递给你一个视角"等步骤感话术。命中后 EX 最高 1。
  例如："你有没有想过老师为什么这样？"、"我想轻轻递给你一个视角"。
- low_pressure_binary_question：具体、低压、学生能直接回答的二选一问题本身不应被惩罚；只有学生可以不加推理直接回答的具体二选一才能标此标签。
  例如："是不想吵，还是觉得说了也没用？"。反例："你觉得她是什么意思？"、"你有没有想过他为什么这样？"。

评分执行要求：
1. IP=2 只给有文本依据的隐含情绪或担忧命名，例如从"朋友没叫我"贴合地指出"被排除、被忽视的难受"。
2. 无依据动机推断、人格结论或因果解释不能算 IP=2。
3. 不要因为出现"我理解""换谁都会""说明你很在乎""挺难得""不用急"就自动给 ER/IP 高分。
4. 如果 rationale 识别到模板化、第三方解释、事实补全、强行重构或成人 coaching，分数必须体现对应降分。
5. ER/IP 边缘判分一致性：只是准确描述、分析或复述情绪时默认落在 1；ER=2 需要额外满足陪伴感，IP=2 需要额外满足未明说洞察。
"""

F9_AUDIT_TAGS = {
    "template_low_information",
    "forced_positive_reframe",
    "unsupported_third_party_motive",
    "third_party_excuse",
    "unsupported_fact_completion",
    "hard_boundary_fabrication",
    "relationship_decision_risk",
    "adult_coaching_question",
    "low_pressure_binary_question",
}

F9_ER_IP_CAP_TAGS = {
    "template_low_information",
    "forced_positive_reframe",
    "unsupported_fact_completion",
    "hard_boundary_fabrication",
    "relationship_decision_risk",
}


class CriticService:
    def __init__(
        self,
        llm_client: LLMClientProtocol,
        critic_run_dao,
        settings: Settings,
    ):
        self.llm_client = llm_client
        self.critic_run_dao = critic_run_dao
        self.settings = settings

    async def evaluate(self, request: CriticEvaluateRequest) -> CriticEvaluateResponse:
        scores = [
            await self._score_candidate(request, candidate)
            for candidate in request.candidates
        ]
        valid_scores = [score for score in scores if not score.boundary_flag]

        best_candidate_id: str | None = None
        fallback_message = ""
        if valid_scores:
            best_score = max(valid_scores, key=lambda score: score.weighted_total)
            best_candidate_id = best_score.candidate_id
        else:
            fallback_message = CRITIC_FALLBACK_MESSAGE

        preference_pair = self._build_preference_pair(valid_scores)
        response = CriticEvaluateResponse(
            best_candidate_id=best_candidate_id,
            scores=scores,
            preference_pair=preference_pair,
            fallback_message=fallback_message,
        )
        if self.critic_run_dao is not None:
            await self.critic_run_dao.create_run(
                session_id=request.session_id,
                user_message=request.user_message,
                history=[item.model_dump() for item in request.history],
                activated_casel=request.activated_casel,
                candidates=[candidate.model_dump() for candidate in request.candidates],
                scores=[score.model_dump() for score in scores],
                best_candidate_id=best_candidate_id,
                preference_pair=(
                    preference_pair.model_dump() if preference_pair is not None else None
                ),
                fallback_message=fallback_message,
            )
        return response

    async def _score_candidate(
        self, request: CriticEvaluateRequest, candidate: CandidateInput
    ) -> CandidateScore:
        format_artifact_reason = self._format_artifact_reason(candidate.text)
        if format_artifact_reason:
            return CandidateScore(
                candidate_id=candidate.candidate_id,
                epitome=EpitomeScore(ER=0, IP=0, EX=0),
                casel={},
                boundary_flag=True,
                boundary_reason=format_artifact_reason,
                weighted_total=0.0,
                rationale=format_artifact_reason,
            )

        prompt_leak_reason = self._internal_prompt_leak_reason(candidate.text)
        if prompt_leak_reason:
            return CandidateScore(
                candidate_id=candidate.candidate_id,
                epitome=EpitomeScore(ER=0, IP=0, EX=0),
                casel={},
                boundary_flag=True,
                boundary_reason=prompt_leak_reason,
                weighted_total=0.0,
                rationale=prompt_leak_reason,
            )

        samples = []
        for _ in range(self.settings.CRITIC_SAMPLE_COUNT):
            samples.append(await self._score_once(request, candidate))

        er = int(median(sample["ER"] for sample in samples))
        ip = int(median(sample["IP"] for sample in samples))
        ex = int(median(sample["EX"] for sample in samples))
        casel = self._median_casel_scores(samples, request.activated_casel)
        boundary_samples = [sample for sample in samples if sample["boundary_flag"]]
        boundary_flag = bool(boundary_samples)
        boundary_reason = (
            str(boundary_samples[0]["boundary_reason"]) if boundary_samples else ""
        )
        rationale = str(samples[0].get("rationale", ""))
        weighted_total = float(er + ip + ex + self._casel_bonus(casel))

        return CandidateScore(
            candidate_id=candidate.candidate_id,
            epitome=EpitomeScore(ER=er, IP=ip, EX=ex),
            casel=casel,
            boundary_flag=boundary_flag,
            boundary_reason=boundary_reason,
            weighted_total=weighted_total,
            rationale=rationale,
        )

    @staticmethod
    def _casel_bonus(casel: dict[str, int]) -> float:
        if not casel:
            return 0.0
        return CASEL_TOTAL_WEIGHT * (sum(casel.values()) / len(casel))

    async def _score_once(
        self, request: CriticEvaluateRequest, candidate: CandidateInput
    ) -> dict:
        try:
            raw_response = await self.llm_client.generate(
                prompt=self._build_prompt(request, candidate),
                timeout=self.settings.CRITIC_LLM_TIMEOUT,
                temperature=self.settings.CRITIC_LLM_TEMPERATURE,
                max_tokens=self.settings.CRITIC_LLM_MAX_TOKENS,
                response_format=(
                    {"type": "json_object"}
                    if self.settings.CRITIC_LLM_RESPONSE_FORMAT_JSON
                    else None
                ),
            )
            return self._parse_score(raw_response)
        except ValueError:
            return self._failed_score("llm_parse_failure")
        except Exception:
            return self._failed_score("llm_failure")

    def _build_prompt(
        self, request: CriticEvaluateRequest, candidate: CandidateInput
    ) -> str:
        history_text = "\n".join(f"{item.role}: {item.text}" for item in request.history)
        casel_prompt = self._build_casel_prompt(request.activated_casel)
        return f"""你是一个情感教育系统的回应质量评估模块，面向中国初中生（12–15岁）。给定用户的倾诉和一条候选回应，你要按 EPITOME 框架为这条回应打分。你不改写回应，只打分。

【EPITOME 三个维度，每维打 0 / 1 / 2】
- ER 情绪反应：回应是否表达温暖、关切，并让孩子读完有"有人在陪我、在乎我"的感觉。0=冷漠无关切；1=准确说出、分析或深化了孩子的情绪，但读起来像旁观者在描述他的状态，没有真正陪伴感（只换词复述情绪、只点出情绪就转去分析或提问，都属于这一档）；2=既贴合地接住情绪，又让孩子感到有人陪着他、关心他。判断方法：把这句话读给一个正难受的孩子，他会觉得"这人懂我，而且在乎我"给2，还是"这人说得对，但跟我没关系"给1。
- IP 解释：回应是否传达"理解了对方的处境和感受"，且点出的是对方没有明说的那层。0=误解或答非所问；1=只复述对方已经明说的事实或情绪（对方已说"气死了""是不是我哪里不好"，回应只是换词重述），或只停留在表面；2=准确点出孩子没有明说、但藏在话里的情绪或担忧。
- EX 探索：回应是否邀请对方进一步表达。0=关闭对话或转移；1=没有主动探索；2=用开放式问题温和引导对方多说（对初中生要温和，不要像审问）。

【打分原则】
1. 只根据回应文本打分，不脑补回应里没有的内容。
2. 不要因为回应更长就给更高分。
3. 三个维度各自独立打分。
4. 同时检查：回应是否包含不适合初中生的内容、是否有事实编造、是否越界（如替代专业心理治疗、鼓励隐瞒家长老师）。若有，单独标记。
5. 硬边界：内部提示外泄、prompt 痕迹、面向开发者或教师的元话术必须标记 `boundary_flag=true`，例如"如果孩子想继续，可以追问""建议回复""候选""策略"或括号式教师提示。
6. 硬边界：整段回复被引号包裹、明显异常换行或格式损坏必须标记 `boundary_flag=true`，`boundary_reason="format_artifact"`；句中正常引用孩子的话不算格式异常。
7. 硬边界：严重事实编造必须标记 `boundary_flag=true`，包括用户未提及的数量、科目、排序、具体行为、现实安排，或把用户未提及的第三方动机写成事实并影响行动/安全判断。普通事实补全按 F9 audit_tags 降分，不自动出局。
8. 即使 ER/IP/EX 分数较高，只要命中任一硬边界，也必须 `boundary_flag=true`，不得因为共情或探索表现好而放行。
{F9_RELIABILITY_SCORING_GUARDRAILS}
{casel_prompt}

请输出严格 JSON：
{{
  "ER": 0/1/2, "IP": 0/1/2, "EX": 0/1/2,
  "casel": {{"仅包含activated_casel中的维度名": 0/1/2}},
  "audit_tags": ["只能使用上面列出的标签；没有命中则为空数组"],
  "boundary_flag": true/false,
  "boundary_reason": "若flag为true，说明原因；否则空字符串",
  "rationale": "一句话中文理由"
}}

【用户倾诉】{request.user_message}
【对话历史】{history_text}
【候选回应】{candidate.text}
"""

    def _parse_score(self, raw_response: str) -> dict:
        data = json.loads(self._extract_json(raw_response))
        parsed = {
            "ER": self._score_value(data.get("ER")),
            "IP": self._score_value(data.get("IP")),
            "EX": self._score_value(data.get("EX")),
            "casel": data.get("casel", {}),
            "boundary_flag": bool(data.get("boundary_flag", False)),
            "boundary_reason": str(data.get("boundary_reason", "")),
            "rationale": str(data.get("rationale", "")),
            "audit_tags": self._normalize_audit_tags(data.get("audit_tags", [])),
        }
        return self._apply_f9_score_caps(parsed)

    @staticmethod
    def _build_casel_prompt(activated_casel: list[str]) -> str:
        active_rubric = [
            f"- {dimension}：{CASEL_RUBRIC[dimension]}"
            for dimension in activated_casel
            if dimension in CASEL_RUBRIC
        ]
        if not active_rubric:
            return ""
        return f"""

【CASEL 辅助维度，每维打 0 / 1 / 2】
本轮只评以下被激活的维度，不要输出其他 CASEL 维度：
{chr(10).join(active_rubric)}
"""

    @staticmethod
    def _extract_json(raw_response: str) -> str:
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("no json object")
        return raw_response[start : end + 1]

    @staticmethod
    def _score_value(value) -> int:
        score = int(value)
        if score < 0 or score > 2:
            raise ValueError("score out of range")
        return score

    @classmethod
    def _safe_epitome_value(cls, value) -> int:
        try:
            return cls._score_value(value)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _safe_casel_value(cls, value) -> int:
        try:
            return cls._score_value(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _normalize_audit_tags(raw_tags) -> list[str]:
        if not isinstance(raw_tags, list):
            return []
        normalized = []
        for tag in raw_tags:
            tag_text = str(tag).strip()
            if tag_text in F9_AUDIT_TAGS and tag_text not in normalized:
                normalized.append(tag_text)
        return normalized

    @staticmethod
    def _append_audit_rationale(rationale: str, audit_tags: list[str]) -> str:
        if not audit_tags:
            return rationale
        suffix = f"audit_tags={','.join(audit_tags)}"
        if suffix in rationale:
            return rationale
        return f"{rationale} {suffix}".strip()

    @classmethod
    def _internal_prompt_leak_reason(cls, text: str) -> str:
        if any(marker in text for marker in PROMPT_LEAK_MARKERS):
            return INTERNAL_PROMPT_LEAK_REASON
        if BRACKETED_PROMPT_LEAK_RE.search(text):
            return INTERNAL_PROMPT_LEAK_REASON
        return ""

    @staticmethod
    def _format_artifact_reason(text: str) -> str:
        stripped = (text or "").strip()
        if len(stripped) >= 2:
            closing = WRAPPED_RESPONSE_QUOTES.get(stripped[0])
            if closing and stripped.endswith(closing):
                return FORMAT_ARTIFACT_REASON
        if re.search(r"\n\s*\n\s*\n+", stripped):
            return FORMAT_ARTIFACT_REASON
        return ""

    @classmethod
    def _apply_f9_score_caps(cls, score: dict) -> dict:
        capped = dict(score)
        capped["ER"] = cls._safe_epitome_value(capped.get("ER", 0))
        capped["IP"] = cls._safe_epitome_value(capped.get("IP", 0))
        capped["EX"] = cls._safe_epitome_value(capped.get("EX", 0))

        audit_tags = cls._normalize_audit_tags(capped.get("audit_tags", []))
        tag_set = set(audit_tags)

        if tag_set & F9_ER_IP_CAP_TAGS:
            capped["ER"] = min(capped["ER"], 1)
            capped["IP"] = min(capped["IP"], 1)

        if "unsupported_third_party_motive" in tag_set:
            capped["IP"] = min(capped["IP"], 1)

        if "third_party_excuse" in tag_set:
            capped["IP"] = 0

        if "hard_boundary_fabrication" in tag_set:
            capped["boundary_flag"] = True
            capped["boundary_reason"] = (
                capped["boundary_reason"] or "hard_boundary_fabrication"
            )

        if "adult_coaching_question" in tag_set:
            capped["EX"] = min(capped["EX"], 1)

        capped["audit_tags"] = audit_tags
        capped["rationale"] = cls._append_audit_rationale(
            str(capped.get("rationale", "")),
            audit_tags,
        )
        return capped

    @classmethod
    def _normalize_casel(cls, raw_casel, activated_casel: list[str]) -> dict[str, int]:
        if not activated_casel:
            return {}
        if not isinstance(raw_casel, dict):
            raw_casel = {}
        return {
            dimension: cls._safe_casel_value(raw_casel.get(dimension, 0))
            for dimension in activated_casel
        }

    @classmethod
    def _median_casel_scores(
        cls, samples: list[dict], activated_casel: list[str]
    ) -> dict[str, int]:
        if not activated_casel:
            return {}
        normalized_samples = [
            cls._normalize_casel(sample.get("casel", {}), activated_casel)
            for sample in samples
        ]
        return {
            dimension: int(
                median(sample[dimension] for sample in normalized_samples)
            )
            for dimension in activated_casel
        }

    @staticmethod
    def _failed_score(reason: str) -> dict:
        return {
            "ER": 0,
            "IP": 0,
            "EX": 0,
            "casel": {},
            "boundary_flag": True,
            "boundary_reason": reason,
            "rationale": reason,
        }

    @staticmethod
    def _build_preference_pair(
        valid_scores: list[CandidateScore],
    ) -> PreferencePair | None:
        if len(valid_scores) < 2:
            return None
        ranked = sorted(
            valid_scores,
            key=lambda score: score.weighted_total,
            reverse=True,
        )
        if ranked[0].weighted_total == ranked[1].weighted_total:
            return None
        return PreferencePair(
            winner_id=ranked[0].candidate_id,
            loser_id=ranked[1].candidate_id,
        )
