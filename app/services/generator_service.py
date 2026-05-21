import asyncio

from app.config import Settings
from app.schemas.generator import (
    GeneratorCandidate,
    GeneratorGenerateRequest,
    GeneratorGenerateResponse,
    GeneratorOrientation,
)
from app.services.llm_client import LLMClientProtocol


GENERATOR_FALLBACK_TEXT = "我听见你现在有些不容易，我在这里陪你。你愿意再多说一点吗？"

COMMON_PROMPT = """你是一个面向中国初中生（12–15岁）的情感教育陪伴者。你的目标不是替孩子解决问题，而是帮助他们更好地认识、表达和调节自己的情绪。

通用原则：
1. 先共情、先确认情绪，不要急着给建议或说教。
2. 语气温暖、平等，像一个可信任的大朋友，不要居高临下，不要用成年人的官腔。
3. 用初中生能接受的、自然的中文口语，简短为主（2–4句）。
4. 绝不诱导孩子隐瞒家长或老师，绝不制造孩子与可信成年人之间的隔离。
5. 不做专业心理诊断或治疗，不替代专业帮助。
6. 不编造事实，不假装记得没发生过的事。
"""

ORIENTATION_PROMPTS: dict[GeneratorOrientation, str] = {
    "共情型": """【你的取向：共情陪伴】
这一轮你要做的是充分地接住孩子的情绪。重点：
- 准确说出你感受到的他/她的情绪，让对方觉得"被理解了"。
- 表达真诚的关切和陪伴，而不是泛泛的"别难过"。
- 可以温和地邀请对方多说一点，但不要追问式审问。
- 这一轮不急于给方法或建议，让对方先感到被接住。
""",
    "引导反思型": """【你的取向：引导反思】
这一轮你要在共情的基础上，温和地引导孩子自己思考。重点：
- 先简短确认情绪，再用开放式问题帮对方理清自己的想法和感受。
- 引导对方看到不同的角度或可能性，但不要直接给结论、替对方做决定。
- 问题要温和、具体、适合初中生，避免说教感。
- 让对方在你的引导下自己往前走一步，而不是你拉着走。
""",
}

ORIENTATION_ORDER: list[tuple[str, GeneratorOrientation]] = [
    ("c1", "共情型"),
    ("c2", "引导反思型"),
]


class GeneratorService:
    def __init__(self, llm_client: LLMClientProtocol, settings: Settings):
        self.llm_client = llm_client
        self.settings = settings

    async def generate(
        self, request: GeneratorGenerateRequest
    ) -> GeneratorGenerateResponse:
        candidates = await asyncio.gather(
            *[
                self._generate_candidate(request, candidate_id, orientation)
                for candidate_id, orientation in ORIENTATION_ORDER
            ]
        )
        return GeneratorGenerateResponse(candidates=list(candidates))

    async def _generate_candidate(
        self,
        request: GeneratorGenerateRequest,
        candidate_id: str,
        orientation: GeneratorOrientation,
    ) -> GeneratorCandidate:
        try:
            raw_response = await self.llm_client.generate(
                prompt=self._build_prompt(request, orientation),
                timeout=self.settings.LLM_TIMEOUT,
                temperature=self.settings.GENERATOR_LLM_TEMPERATURE,
                max_tokens=self.settings.LLM_MAX_TOKENS,
            )
            text = raw_response.strip()
            if not text:
                raise ValueError("empty generator response")
        except Exception:
            text = GENERATOR_FALLBACK_TEXT
        return GeneratorCandidate(
            candidate_id=candidate_id,
            orientation=orientation,
            text=text,
        )

    def _build_prompt(
        self, request: GeneratorGenerateRequest, orientation: GeneratorOrientation
    ) -> str:
        window_size = self.settings.HISTORY_WINDOW_N * 2
        history = request.history[-window_size:]
        history_text = "\n".join(f"{item.role}: {item.text}" for item in history) or "无"
        rag_text = "\n".join(request.rag_examples) if request.rag_examples else "无"
        return f"""{COMMON_PROMPT}
{ORIENTATION_PROMPTS[orientation]}

【情境】{request.scenario}
【对话历史】{history_text}
【参考（可选，仅供风格参考，不要照抄）】{rag_text}
【孩子刚说的话】{request.user_message}

请按你的取向，生成一条回应：
"""
