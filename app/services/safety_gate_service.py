import json

from app.config import Settings
from app.schemas.safety import SafetyAction, SafetyGateRequest, SafetyGateResponse
from app.services.llm_client import LLMClientProtocol


YELLOW_REFERRAL_MESSAGE = """谢谢你愿意把这些告诉我。听起来你现在很不容易，这些感受很重要，不该一个人扛着。
我想提醒你：和你信任的大人聊聊会很有帮助——可以是爸爸妈妈、老师，或学校的心理辅导老师。
如果你想找人随时说说话，下面的支持资源也可以使用。
你愿意和我说说，是很勇敢的一步。"""

RED_REFERRAL_MESSAGE = """我很担心你现在的安全，你的生命非常重要。
请立刻联系你信任的大人（爸爸妈妈、老师），告诉他们你现在的感受，不要独自面对。
下面的紧急资源现在就可以使用。
你不是一个人，有人愿意帮你。请现在就找一个大人陪你一起处理。"""

SAFETY_UNAVAILABLE_MESSAGE = """当前安全评估暂不可用。为了稳妥，我先不继续生成普通回复。
你可以稍后再试；如果你现在担心自己可能会伤害自己，或无法保证安全，请立刻联系身边可信任的大人、学校老师，或当地紧急服务。"""


class SafetyGateService:
    def __init__(
        self,
        llm_client: LLMClientProtocol,
        safety_log_dao,
        settings: Settings,
    ):
        self.llm_client = llm_client
        self.safety_log_dao = safety_log_dao
        self.settings = settings

    async def evaluate(self, request: SafetyGateRequest) -> SafetyGateResponse:
        prompt = self._build_prompt(request)
        try:
            raw_response = await self.llm_client.generate(
                prompt=prompt,
                timeout=self.settings.LLM_TIMEOUT,
                temperature=self.settings.SAFETY_LLM_TEMPERATURE,
                max_tokens=self.settings.LLM_MAX_TOKENS,
            )
            response = self._parse_response(raw_response)
        except ValueError:
            response = self._fallback_response(
                matched_signal="llm_parse_failure",
                rationale="安全门模型输出无法解析，安全评估暂不可用。",
            )
        except Exception:
            response = self._fallback_response(
                matched_signal="llm_failure",
                rationale="安全门模型调用失败，安全评估暂不可用。",
            )

        if self.safety_log_dao is not None:
            await self.safety_log_dao.create_log(
                session_id=request.session_id,
                risk_level=response.risk_level,
                matched_signals=response.matched_signals,
                rationale=response.rationale,
                block_generation=response.action.block_generation,
                referral_message=response.action.referral_message,
            )
        return response

    def _build_prompt(self, request: SafetyGateRequest) -> str:
        window_size = self.settings.HISTORY_WINDOW_N * 2
        history = request.history[-window_size:]
        history_text = "\n".join(f"{item.role}: {item.text}" for item in history)
        return f"""你是一个面向中国初中生（12–15岁）情感教育系统的安全评估模块。你的唯一任务是评估用户最近的对话中是否存在自伤或自杀风险，并分级。你不与用户对话，只输出评估结果。

请基于【对话历史】和【当前消息】整体判断（风险信号可能分散在多轮中，需结合上下文，不要只看当前一句）。

分级标准（参照哥伦比亚自杀风险评估 C-SSRS）：
- green（无风险）：正常的情绪困扰、压力、烦躁、难过，但没有任何伤害自己的想法或表达。
- yellow（需关注）：出现被动或主动的自伤/自杀念头，但没有具体计划、意图或准备行为。例如表达"活着没意思""不想存在了""消失算了"等，但无进一步计划。
- red（高危）：出现自伤/自杀的意图、具体计划、方法、时间，或已有准备/尝试行为，或正在进行的伤害。

判定原则：
1. 分级要准确，不要把单纯的情绪宣泄（如"烦死了""我太菜了""不想上学"）误判为风险。
2. 但凡出现模糊的伤害自己的表达，宁可判 yellow 也不要漏判。
3. 只依据文本证据判断，不脑补。
4. 若不确定是 yellow 还是 red，从严判 red。

请输出严格的 JSON：
{{
  "risk_level": "green/yellow/red",
  "matched_signals": ["命中的具体表达，逐条列出；green时为空数组"],
  "rationale": "一句话中文理由"
}}

【对话历史】
{history_text}

【当前消息】
{request.current_message}
"""

    def _parse_response(self, raw_response: str) -> SafetyGateResponse:
        data = json.loads(self._extract_json(raw_response))
        risk_level = data.get("risk_level")
        if risk_level not in {"green", "yellow", "red"}:
            raise ValueError("invalid risk_level")
        matched_signals = data.get("matched_signals", [])
        if not isinstance(matched_signals, list):
            raise ValueError("matched_signals must be list")
        rationale = str(data.get("rationale", "")).strip() or "无详细理由。"
        return self._response(
            risk_level=risk_level,
            matched_signals=[str(signal) for signal in matched_signals],
            rationale=rationale,
        )

    @staticmethod
    def _extract_json(raw_response: str) -> str:
        start = raw_response.find("{")
        end = raw_response.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise ValueError("no json object")
        return raw_response[start : end + 1]

    def _fallback_response(self, matched_signal: str, rationale: str) -> SafetyGateResponse:
        return self._response(
            risk_level="yellow",
            safety_status="unavailable",
            matched_signals=[matched_signal],
            rationale=rationale,
        )

    @staticmethod
    def _response(
        risk_level: str,
        matched_signals: list[str],
        rationale: str,
        safety_status: str = "ok",
    ) -> SafetyGateResponse:
        if safety_status == "unavailable":
            action = SafetyAction(
                block_generation=True,
                referral_message=SAFETY_UNAVAILABLE_MESSAGE,
            )
        elif risk_level == "green":
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
            safety_status=safety_status,  # type: ignore[arg-type]
            matched_signals=matched_signals,
            rationale=rationale,
            action=action,
        )
