import asyncio
import hashlib
import re

from app.config import Settings
from app.schemas.generator import (
    GeneratorCandidate,
    GeneratorGenerateRequest,
    GeneratorGenerateResponse,
    GeneratorOrientation,
)
from app.services.f3_support_service import F3SupportService
from app.services.llm_client import LLMClientProtocol


GENERATOR_FALLBACK_TEXT = "我听见你现在有些不容易，我在这里陪你。你愿意再多说一点吗？"
WRAPPED_RESPONSE_QUOTES = {
    '"': '"',
    "'": "'",
    "“": "”",
    "「": "」",
    "『": "』",
}

COMMON_PROMPT = """你是一个面向中国初中生（12–15岁）的情感陪伴者。目标不是替孩子解决问题，而是让他感到被理解，并慢慢学会认识、表达自己的情绪。

通用原则：
1. 紧扣孩子刚说的那句话里的具体内容回应，不要说放在谁身上都成立的万能话。
2. 优先具体承接孩子说出的场景和感受，不强求以夸奖开头。可以轻轻肯定孩子愿意说出来、把事情讲清楚、能觉察到自己的感受；不要把"哇"、"其实你"或品质化夸奖作为默认开头，更多时候直接从孩子说的具体内容切入。
3. 语气像一个可信任、稍年长的朋友：平等、自然、软。绝不居高临下、绝不打官腔、绝不说教。
4. 用初中生平时会说的口语，短，2–3句。
5. 绝不诱导孩子隐瞒家长或老师，绝不在孩子和可信成年人之间制造隔阂。
6. 不做心理诊断或治疗，不替代专业帮助；不得编造用户未说的事实，不假装记得没发生过的事；不推测孩子没说出口的外部事实或他人动机。
7. 最终回复只包含直接对学生说的话；禁止内部提示外泄，不要写"如果孩子想继续""可以追问""建议回复""候选""策略"这类面向老师、评审或开发者的元说明，也不要用括号补充教师提示。不要写括号式阶段标签，例如"（先接住你的场景）""（再递新视角）""（共情）""（提问）"。
8. 不能把推测写成事实；不能创造用户没说过的数量、科目、顺序、具体行为或第三方心理。
9. 不要数孩子刚说的话有几个字，也不要写"这三个字""这四个字"这类精确字数判断；需要指代时用"这句话"或"你刚才这句"。
10. 语气少评价、少说教、少替第三方解释，多承接孩子感受。少用"挺厉害""很清醒"这类评价式夸奖，多用更轻的感受承接。

【禁用】
- 万能空话："听起来你很难受""我在这儿陪着你""别太难过""我理解你的感受"。把"难受"换成你从他话里读到的、具体的那一种。
- 说教式判语句式："这不是A，而是B""你要明白……""其实你应该……"。
- 替第三方解释或开脱："他可能只是……""大人也许……"。没有证据时，不猜朋友、同学、家长、老师的真实想法或动机。
- 内部提示或元说明："如果孩子想继续，可以追问……""建议回复……""可继续引导……""（先接住你的场景）""（再递新视角）"。这些内容不能出现在最终回复中。
"""

F9_RELIABILITY_GUARDRAILS = """【F9 信度修订后的额外约束】
- 先承接，再理解；不要用“说明你”“可见你”“这本身”把孩子的痛苦总结成品质、能力或优点。
- 承接必须包含对孩子说出的那一件具体的事的复述——用你自己的话点回他刚讲的那个具体场景或动作（他翻了好几遍群、他被点名时周围有人笑、他把手机放下的那一下），让他认出“对，这就是我刚说的那件事”。“换谁都会”“这种感觉很正常”“都会觉得难受”这类放在谁身上都成立的句子，最多只能跟在具体复述后面作补充，绝不能单独充当承接。判断标准：把你承接的那一两句单独拿出来，如果它套在任何一个同类处境的孩子身上都成立，说明你还没真正接住眼前这一个孩子，重写。
- 未充分承接情绪前，不要把痛苦、自责、愤怒或不信任直接重构成优点、主见、判断力或在乎别人。
- 未充分承接情绪前，不要把痛苦、自责、愤怒、不信任、沉默或反复确认改写成判断力、懂事、很有数、有主见或在乎别人。
- 不要把抱怨、愤怒、自责、沉默、反复确认改写成判断力、懂事、很有数或有主见。
- 肯定只能落在孩子明确说出的动作、感受或表达本身，例如“你把这件事说得很具体”“你把那股不公平感讲出来了”；不要替孩子下人格结论。
- 轻量稳定感可以使用，但前面必须已经具体回应当前倾诉；不要用“说明你很在乎”“你已经很不容易”“先缓一缓也没关系”替代真正回应。
- 二选一问题必须同时满足：两个选项都是孩子真实面临的处境、彼此互斥、任一答案都能推进孩子继续表达；不满足就不要发问，退回成“补一个孩子没注意到的、关于他自己感受/需要/可控边界的可能性陈述”。不要把因果关系硬拆成二选一，也不要替第三方解释动机、替学生下人格或关系结论。
- 涉及朋友、同学、家长、老师时，只说孩子感受到的影响和可控边界，不替对方找理由，不把冲动断关系、报复、羞辱包装成“有主见”。
"""

DIALOGUE_STAGE_GUIDANCE = {
    "first_contact": (
        "这是本次会话第一次回应。优先让孩子觉得这句话真的接住了他，"
        "少问问题，默认不用反问句；如果必须问，也只能是一个很低压力、能继续表达的小问题。"
        "不要急着给步骤化建议。"
    ),
    "follow_up": (
        "这是持续对话中的后续回应。不要只重复安慰；先短短承接，再帮孩子把"
        "感受、想法、身体/行为反应或可控边界分清楚，必要时给一个很小、可选择的下一步。"
        "不要把这写成治疗说明，也不要显性说 CBT。"
    ),
}

SUPPORT_MODE_GUIDANCE = {
    "emotion_first": (
        "用户当前消极情绪较强或主要在倾诉。c1 应更有情感认同和稳定感；"
        "c2 也要先放软，不要急着剖析或给答案。"
    ),
    "solution_seeking": (
        "用户明确在问怎么办或怎么改变。c2 应把卡住点和可能的担心说准，"
        "可以给一个不命令、不越界的轻量起点；c1 仍需承接情绪，但不要停在泛泛安慰。"
    ),
    "balanced": (
        "用户既有情绪也有困惑，或证据不足。先具体承接，再根据取向分别靠近情绪共振或处境澄清。"
    ),
}

EMOTION_INTENSITY_GUIDANCE = {
    "low": "情绪强度较低，回应保持自然，不要把问题严重化。",
    "medium": "情绪强度中等，回应要具体、有温度，同时保持简短。",
    "high": "情绪强度较高，先稳定和承接，不要上来讲道理、追问或给一串办法。",
}

ORIENTATION_PROMPTS: dict[GeneratorOrientation, str] = {
    "共情型": """【你的取向：共情陪伴 —— 全程向内】
这一轮，你唯一的任务是让孩子感到"被稳稳接住"。
- 以一句具体承接开头，先接住他话里最具体的情绪、场景（必须让他认出是他刚说的那件事）；可以轻轻肯定“愿意说出来”或“把事情讲清楚”，但不要开头就评价他的品质、能力或人格。
- 然后把他此刻的感受往深里说一点：替他把那层没说出口、但藏在话里的心情说出来。
- 全程只停在"此刻"。不要问任何问题，不要给任何建议、方法或新角度，不要任何"往前看""换个想法"的成分。
- 先识别主导情绪再决定收尾：难过、委屈、孤独时，可以给轻轻的安稳感；愤怒或不公感很强时，认可这股气的正当性，例如“这股气是有道理的”，不要用“停在这里也没关系”“这样也没什么不对”这类安抚收尾。
成功的标志：孩子读完心里"嗯，对，就是这样"，并松一口气。
""",
    "引导反思型": """【你的取向：引导反思 —— 重心向外】
这一轮，你要在轻轻接住情绪后，给孩子打开一个他自己没注意到的新视角。
- 开头先用一句具体复述接住情绪：哪怕只有一句，这一句也必须点回孩子刚说的那个具体场景或动作，不能用"换谁都会""这种事很常见"这类泛化句顶替。引导反思型的承接可以短，但不能空——短指的是不展开第二层情绪，不是把承接换成一句谁都适用的安慰。
- 承接落地之后，再转向新视角；如果你发现自己写的承接套在任何同类孩子身上都成立，说明它还没接住眼前这个孩子，先把那一句改具体，再往下写。前半没接住，后面的问题读起来就是审问，不是陪伴。
- 重心放在自然地给孩子打开一个新角度：不要固定使用任何引导套话，尤其不要反复使用"我想轻轻递给你一个想法"、"不过你有没有注意到"。可以根据语境选择更自然的承接方式，例如把两种感受并列、回到孩子的需要或可控边界，或用一个低压力二选一问题。重点是让孩子感觉视角被轻轻打开，而不是听到一段固定话术。
- 新角度只能基于孩子说出的内容和孩子自己的感受，不替朋友、同学、家长或老师解释动机、找理由或开脱；涉及他人时，只描述孩子感受到的影响。
- 这个新角度必须从孩子刚说的话里自然长出来。如果你想不到贴切、不生硬的角度，就退回成一个低门槛的小问题；但问题必须通过二选一门控：两个选项都是孩子真实面临的、彼此互斥、任一答案都能推进对话。任一不满足就不要发问，改成关于孩子自己感受、需要或可控边界的可能性陈述。绝不用"你觉得呢""你怎么想"这种又大又空的问题，并且全程最多只问一个。
- 姿态是陪他站在原地一起看，不是拉他往前跑。绝不追问他想回避的事实细节。
- 生成前自检：如果新角度需要猜他人的心里想法，就换成孩子自己的感受、需要或可控边界；不要写"她其实也……""他可能只是……""大人也许……"这类句子。
- 生成前自检：如果新角度需要补充孩子没说过的事实、数量、科目、顺序或行为，就退回为关于孩子感受的轻问题。
成功的标志：孩子读完"哦……好像也可以这么想"。

【反趋同】你和"共情陪伴"取向同时在回应同一句话。它负责把情绪接到底，你不要重复它的活——你的开头接情绪点到为止（一句具体复述即可），把篇幅留给"递视角"。如果你发现自己写得和一句深度共情几乎一样、只是末尾多了个问题，说明你跑偏了，重写。

【避免模板化】不要让每条回复都用相同开头或相同过渡句。示例短语只代表语气，不是必须照抄的句式。
""",
}

ORIENTATION_ORDER: list[tuple[str, GeneratorOrientation]] = [
    ("c1", "共情型"),
    ("c2", "引导反思型"),
]
ORIENTATION_BY_ID: dict[str, GeneratorOrientation] = dict(ORIENTATION_ORDER)


def clean_generator_output(raw_text: str) -> str:
    text = (raw_text or "").strip()
    if len(text) >= 2:
        closing = WRAPPED_RESPONSE_QUOTES.get(text[0])
        if closing and text.endswith(closing):
            text = text[1:-1].strip()
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n\s*\n+", "\n", text)
    text = re.sub(
        r"(?:(短短|就|只是|仅仅)?这)[一二两三四五六七八九十百千万\d]+个字",
        lambda match: f"{match.group(1) or ''}这句话",
        text,
    )
    return "\n".join(line.strip() for line in text.split("\n") if line.strip())


def f3_prompt_bundle_text() -> str:
    orientation_text = "\n".join(
        f"{orientation}\n{prompt}"
        for orientation, prompt in sorted(ORIENTATION_PROMPTS.items())
    )
    return f"{COMMON_PROMPT}\n{F9_RELIABILITY_GUARDRAILS}\n{orientation_text}"


def f3_prompt_bundle_hash() -> str:
    return hashlib.sha256(f3_prompt_bundle_text().encode("utf-8")).hexdigest()


class GeneratorService:
    def __init__(
        self,
        llm_client: LLMClientProtocol,
        settings: Settings,
        f3_support_service: F3SupportService | None = None,
    ):
        self.llm_client = llm_client
        self.settings = settings
        self.f3_support_service = f3_support_service

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

    async def generate_one(
        self, request: GeneratorGenerateRequest, candidate_id: str = "c2"
    ) -> GeneratorCandidate:
        orientation = ORIENTATION_BY_ID.get(candidate_id, ORIENTATION_ORDER[-1][1])
        return await self._generate_candidate(request, candidate_id, orientation)

    async def generate_followup(
        self,
        *,
        session_id: str,
        user_message: str,
        history: list,
        f4_guidance: str = "",
    ) -> GeneratorCandidate:
        try:
            raw_response = await self.llm_client.generate(
                prompt=self._build_followup_prompt(
                    user_message=user_message,
                    history=history,
                    f4_guidance=f4_guidance,
                ),
                timeout=self.settings.LLM_TIMEOUT,
                temperature=self.settings.GENERATOR_LLM_TEMPERATURE,
                max_tokens=min(self.settings.LLM_MAX_TOKENS, 520),
            )
            text = clean_generator_output(raw_response)
            if not text:
                raise ValueError("empty follow-up response")
        except Exception:
            text = GENERATOR_FALLBACK_TEXT
        return GeneratorCandidate(
            candidate_id="cbt",
            orientation=ORIENTATION_BY_ID.get("c2", ORIENTATION_ORDER[-1][1]),
            text=text,
        )

    async def stream_one_text(
        self, request: GeneratorGenerateRequest, candidate_id: str = "c2"
    ):
        orientation = ORIENTATION_BY_ID.get(candidate_id, ORIENTATION_ORDER[-1][1])
        prompt = self._build_prompt(request, orientation)
        yielded = False
        try:
            async for event in self.llm_client.stream_generate(
                prompt=prompt,
                timeout=self.settings.LLM_TIMEOUT,
                temperature=self.settings.GENERATOR_LLM_TEMPERATURE,
                max_tokens=self.settings.LLM_MAX_TOKENS,
            ):
                if event.get("type") == "delta" and event.get("text"):
                    yielded = True
                    yield str(event["text"])
        except Exception:
            if not yielded:
                yield GENERATOR_FALLBACK_TEXT

    async def stream_followup_text(
        self,
        *,
        user_message: str,
        history: list,
        f4_guidance: str = "",
    ):
        prompt = self._build_followup_prompt(
            user_message=user_message,
            history=history,
            f4_guidance=f4_guidance,
        )
        yielded = False
        try:
            async for event in self.llm_client.stream_generate(
                prompt=prompt,
                timeout=self.settings.LLM_TIMEOUT,
                temperature=self.settings.GENERATOR_LLM_TEMPERATURE,
                max_tokens=min(self.settings.LLM_MAX_TOKENS, 520),
            ):
                if event.get("type") == "delta" and event.get("text"):
                    yielded = True
                    yield str(event["text"])
        except Exception:
            if not yielded:
                yield GENERATOR_FALLBACK_TEXT

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
            text = clean_generator_output(raw_response)
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
        dialogue_stage = normalize_dialogue_stage(request.dialogue_stage)
        support_mode = request.support_mode
        emotion_intensity = request.emotion_intensity
        strategy_prior_text = "无"
        if self.f3_support_service is not None:
            support_context = self.f3_support_service.build_context(
                scenario=request.scenario,
                user_message=request.user_message,
                external_examples=request.rag_examples,
            )
            strategy_prior_text = support_context.strategy_prior or "无"
            rag_text = support_context.support_cards_text
        else:
            rag_text = "\n".join(request.rag_examples) if request.rag_examples else "无"
        return f"""{COMMON_PROMPT}
{F9_RELIABILITY_GUARDRAILS}
{ORIENTATION_PROMPTS[orientation]}

【情境】{request.scenario}
【本轮对话阶段】{dialogue_stage}：{DIALOGUE_STAGE_GUIDANCE[dialogue_stage]}
【本轮支持路由】{support_mode}：{SUPPORT_MODE_GUIDANCE[support_mode]}
【情绪强度】{emotion_intensity}：{EMOTION_INTENSITY_GUIDANCE[emotion_intensity]}
【是否明确求助】{"是" if request.help_seeking else "否"}
【对话历史】{history_text}
【策略先验（来自 PsyQA 标注统计，只作内部生成约束）】{strategy_prior_text}
【PsyQA 支持卡（可选，仅供语言动作和风格参考，不要照抄）】{rag_text}
【孩子刚说的话】{request.user_message}

请按你的取向，生成一条回应：
"""

    def _build_followup_prompt(
        self,
        *,
        user_message: str,
        history: list,
        f4_guidance: str = "",
    ) -> str:
        window_size = self.settings.HISTORY_WINDOW_N * 2
        history_text = "\n".join(
            f"{getattr(item, 'role', 'message')}: {getattr(item, 'text', '')}"
            for item in history[-window_size:]
        )
        guidance_text = f4_guidance.strip() or "No completed critic guidance yet."
        return f"""You are a Chinese educational emotional-support agent for middle-school students.
This is a follow-up turn, so do not rerun the full multi-agent workflow. Give one direct student-facing reply in Simplified Chinese.

Use a CBT-informed style without naming CBT:
- briefly connect the concrete situation, thought or worry, feeling, and one controllable next step;
- do not diagnose, do not mention therapy, models, prompts, CASEL, EPITOME, or critic;
- do not ask broad rhetorical questions; at most ask one small, concrete, low-pressure question;
- keep it short and readable, usually 2 to 4 short sentences;
- avoid long lists unless the student clearly asks for steps;
- if there is clear self-harm or imminent danger, stop ordinary coaching and encourage telling a trusted adult or emergency support immediately.

Use completed F4 guidance only if it is available. If it is pending or empty, ignore it.
F4 guidance:
{guidance_text}

Recent conversation:
{history_text or "No prior history."}

Current student message:
{user_message}

Reply only with the final Chinese message for the student.
"""


def normalize_dialogue_stage(value: str) -> str:
    return "follow_up" if value == "follow_up" else "first_contact"
