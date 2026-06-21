# 前端模块 · Claude Code 开发规格（学生端 + 研究分析台）

> **交付对象**：Claude Code / 编码 agent。本文档自包含，实现前端无需阅读其他文档（后端接口契约见 §3，已与 F1–F4 现有 schema 对齐）。
> **模块定位**：系统的两个前端入口。学生端是产品；研究分析台是离线工具。二者共享一个后端 `/chat`，但**物理分离、数据通路不同**。
> **技术栈**：React 18 + Vite + TypeScript（建议）；后端复用现有 FastAPI（`POST /chat` 和推荐的 `POST /chat/stream`）。无需新增后端端点即可跑通学生端。

---

## 1. 一句话职责

把两个已设计好的 React 原型（`EmoAgentStudent.jsx`、`ResearchConsole.jsx`）接到真实 FastAPI：学生端只通过 narrowed student API 获取 `StudentChatView` 或 SSE 文本增量，渲染 `reply_text` 与危机转介；研究分析台渲染全部分析字段（候选、EPITOME/CASEL 分数、择优、批量统计）。**学生端在代码层禁止 import 或渲染任何分析字段。**

---

## 2. 两个入口的边界（核心安全约束，必须遵守）

| 维度 | 学生端 EmoAgent | 研究分析台 |
|---|---|---|
| 使用者 | 初中生（12–15） | 研究者 / 开发者 / 评委 |
| 部署 | 独立前端，面向公网 | 独立前端，内网 / 离线 / 鉴权后 |
| 可用字段 | **仅** `reply_text`、`risk_level`（用于触发转介）、`session_id`、`anonymous_user_id`（仅用于连续性） | 全部：`candidates`、`scores`、`epitome`、`casel`、`weighted_total`、`boundary_flag`、`preference_pair`、批量统计 |
| 数据通路 | 推荐 `POST /chat/stream`；`POST /chat` 仅作兼容 | `POST /chat`（单轮）+ 读落库的 `turns/candidates/scores/preference_pairs`（批量） |
| 路由 | `/`（或独立域名） | `/console`（或独立域名 + 鉴权） |

> **铁律**：学生端只能 import `fetchStudentChat` / `fetchStudentChatStream` / `clearAnonymousMemory` 和窄类型；`StudentChatView` 只允许包含 `reply_text`、`risk_level`、`session_id`、`anonymous_user_id`。即使后端 `/chat` 返回了 `scores` 等字段，学生端也必须在类型层与渲染层双重丢弃，**绝不能有任何代码路径把分析数据带到学生界面**。这是儿童安全约束，不是工程偏好。

---

## 3. 后端接口契约（与现有 F1–F4 对齐，勿改）

### 3.1 请求
```json
POST /chat
{
  "session_id": "string",       // 同一会话多轮复用同一 id（会话内记忆）
  "anonymous_user_id": "string | null", // 无登录连续性，可省略
  "current_message": "string"
}
```

### 3.2 响应（`ChatResponse`，字段同现有后端）
```json
{
  "session_id": "string",
  "anonymous_user_id": "string | null",
  "status": "answered | blocked_by_safety | all_candidates_blocked | module_failed",
  "reply_text": "string",
  "risk_level": "green | yellow | red",
  "scenario": "学业压力 | 同伴关系 | 亲子摩擦 | 其他 | null",
  "activated_casel": ["string"],
  "best_candidate_id": "string | null",
  "candidates": [
    {"candidate_id": "c1", "orientation": "共情型", "text": "string"},
    {"candidate_id": "c2", "orientation": "引导反思型", "text": "string"}
  ],
  "scores": [
    {
      "candidate_id": "c1",
      "epitome": {"ER": 0, "IP": 0, "EX": 0},
      "casel": {"自我觉察引导": 0},
      "boundary_flag": false,
      "boundary_reason": "",
      "weighted_total": 0.0,
      "rationale": "string"
    }
  ],
  "preference_pair": {"winner_id": "c1", "loser_id": "c2"},
  "failed_module": "string | null",
  "failure_reason": ""
}
```

### 3.3 学生端只用窄字段
学生端从上面的响应或 stream `done` 事件里**只取** `reply_text`、`risk_level`、`session_id`、`anonymous_user_id`。其中 `anonymous_user_id` 只用于本地连续性和清理请求，不作为可见分析字段。逻辑：
- `risk_level === "green"` → 把 `reply_text` 作为一条 AI 消息渲染。
- `risk_level === "yellow"` → 渲染 `reply_text`，同时显示可收起的支持资源卡；输入框保持可用，`status` 通常仍为 `answered`。
- `risk_level === "red"` → 渲染固定转介回复后，弹出固定转介面板（§5.3）并替换输入框；`status` 此时为 `blocked_by_safety`，无候选，正常。

---

## 4. 文件结构（建议）

```
frontend/
  shared/
    api.ts            # fetchChat() + narrowed student wrappers；MOCK/LIVE 切换
    types.ts          # ChatResponse 等共享类型
    samples.ts        # 演示样例（含 syn_0007/0021/0032/crisis）
  student/            # 独立可部署
    EmoAgentStudent.tsx
    main.tsx          # 仅挂载学生端
  console/            # 独立可部署
    ResearchConsole.tsx
    main.tsx          # 仅挂载分析台
```

> 学生端与分析台**不共享组件**，只共享 `shared/`。`shared/types.ts` 里学生端用的窄类型与分析台用的全类型分开导出，从类型层强制 §2 铁律。

---

## 5. 学生端 EmoAgent 实现要点

### 5.1 视觉设计（已锁定，勿自由发挥）
- **暖白打底**（`#faf8f3`，非纯白），鼠尾草绿（`#6f9c80`）**仅作点睛**（logo 点、AI 标记、发送键、一处氛围光），**绝不大面积填充**。
- AI 回复作为「被设计的对象」：带 `EmoAgent` 小标记、字号 17px、行距 1.85；用户消息是右侧低调浅灰气泡。
- 不用纯黑（文字 `#33312c`）、阴影带色不用灰、圆角统一。
- 设计依据见原型注释；改色前先读注释里的研究结论（高饱和暖色升焦虑、低饱和多 pastel + 暖中性为解）。

### 5.2 会话与记忆
- **会话内记忆（现在做）**：前端为每个会话生成 `session_id`，同一会话所有轮次复用它；同一浏览器保留一个 `anonymous_user_id` 用于未登录连续性与清理。后端 Redis 窗口（`HISTORY_WINDOW_N=6`）自动吃历史。前端把同 `session_id` 的多轮顺序渲染即可。
- **侧边栏历史**：`最近聊过` 列出本设备已有会话（标题取首条用户消息），只用于快速回到对话。「开启新对话」生成新 `session_id`。
- **整理记录**：底部工具入口，用于说明本地记录边界、展示本地会话摘要，并提供「让我忘记」清除本设备会话文本；不作为第二个历史列表入口。
- **长期记忆（主动不做）**：不持久化任何跨会话用户画像、情绪轨迹或个性化记忆。学生端只保留本地会话标题与消息文本，并可通过「让我忘记」清除。此决策用于避免诱导情感依赖、避免给波动期青少年固化标签，并最小化未成年人敏感数据留存。

### 5.3 危机转介（安全红线，固定不可改）
- `risk_level` 为 yellow 时，渲染 `reply_text` 后弹出可收起支持资源卡，输入框保持可用。
- `risk_level` 为 red 时，渲染固定转介回复后弹出转介面板，**替换输入框**（禁止继续输入，呼应「红色绝不自行展开危机对话」）。
- 面板含：标题、共情句、可执行引导（联系可信成年人）、两个可拨打按钮 `tel:12356` / `tel:12355`；red 额外提示 120/110。
- 文案用原型 `REFERRAL` 常量，**号码硬编码**，不经任何动态生成。

### 5.4 附加功能
- **低门槛起手式**：空状态显示「今天有点累 / 想吐槽一件事 / 只是想有人在」等入口，点击即发送。
- **整理记录**：见 §5.2 本地记录管理。它不是情绪分析、不是画像记忆，也不消费跨会话画像数据。
- **呼吸小工具**：纯前端动画（8s 一吸一呼），无后端依赖；对应 CASEL 自我管理。

### 5.5 失败兜底
- `/chat` 超时 / 异常 / `status==="module_failed"` → 显示安全兜底话术（「我现在有点没反应过来，要不你再说一次？」），**绝不向学生暴露原始错误或 `failure_reason`**。
- 网络或解析失败时沿用最后一次已知 `risk_level`，不得静默伪装成 `green`。若上一轮已非 green，转介锁维持；只有新会话或显式 reset 才回到 green。

---

## 6. 研究分析台实现要点

### 6.1 三视图
- **单轮追踪**：选一条样例 → 按 F1→F2→F3→F4 分阶段揭示（安全门分级 / 情境+激活 CASEL / 双候选 / critic 打分择优 / preference_pair）。头部显示学生输入，尾部显示学生最终收到的 `reply_text`，形成闭环。
- **批量总览**：读一次 45 条验收 run 的聚合结果——情境分类准确率（总体 + 分情境）、落库计数、boundary 拦截、缺陷闭环记录。数据可来自落库查询或预生成的 summary JSON。
- **框架对标**：C-SSRS 三级、EPITOME 三维（按情感/认知共情分组，标注 IP 可靠性 limitation）、CASEL 情境→维度映射。静态内容。

### 6.2 数据来源
- 单轮：实时 `POST /chat`，渲染完整响应。
- 批量：MVP 使用已记录的验收摘要 `docs/acceptance/orchestrator-mvp/2026-05-21/2026-05-21-orchestrator-mvp-test-summary.md` 作为展示快照；后续可提供只读聚合端点（如 `GET /console/runs/{run_id}/summary`）或导出结果文件。

### 6.3 视觉
- 与学生端**刻意不同**：editorial / 临床研究风（纸感暖底、衬线显示字、信息密度高）。这种反差本身是演示叙事的一部分（产品的温暖 vs 工具的严谨）。

---

## 6.5 模块切换动效

- 学生端与分析台各自实现本地 `TransitionSlot`，不得放入 `shared/`，避免跨端组件耦合。
- 动效只服务模块切换的连续性：学生端用于聊天/记录/呼吸主视图、移动侧栏、composer 与转介面板替换；分析台用于单轮追踪/批量证据/框架对标三视图切换。
- 优先使用 CSS Modules 的 `opacity` + `transform` 过渡；不引入 Framer Motion、GSAP 或 Lottie。
- 过渡时长控制在 140ms–320ms，学生端可更柔和，分析台应克制，保证表格和证据阅读稳定。
- 必须支持 `prefers-reduced-motion: reduce`，降级到近似无动画。
- 继续禁止 `scrollIntoView`，消息滚动仍使用容器 `scrollTop = scrollHeight`。

---

## 7. MOCK / LIVE 切换

```ts
// shared/api.ts
const MODE = import.meta.env.VITE_API_MODE ?? "mock"; // "mock" | "live"

export async function fetchChat(req: ChatRequest): Promise<ChatResponse> {
  if (MODE === "mock") return mockResolve(req);          // 用 samples.ts
  const r = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!r.ok) throw new Error(`chat ${r.status}`);
  return r.json();
}
```
- 学生端 live 模式优先用 `fetchStudentChatStream()` 连接 `/chat/stream`，只把 `delta` 追加进消息，把 `done` 投影为 `StudentChatView`；不得把 `metadata` 或完整 `done` response 渲染给学生。
- 演示现场建议 **mock 优先**（DeepSeek + critic 多采样有数秒延迟，断网即崩），或预录真实响应回放。
- `VITE_API_MODE=live` + `VITE_API_BASE` 指向 FastAPI 即接真后端，前端零改动。

---

## 8. 验收标准（DoD）

学生端：
- [ ] 仅渲染 `reply_text` 和转介所需状态；类型层不含任何分析字段（§2 铁律）。
- [ ] green 正常回复；yellow 显示可收起支持资源卡且输入框可用；red 触发转介面板并锁输入，号码硬编码正确。
- [ ] 同 `session_id` 多轮历史正确串联；「新对话」生成新 id。
- [ ] 侧边栏、本地会话历史、起手式、呼吸工具按 §5 就位。
- [ ] 失败兜底不暴露原始错误。
- [ ] 视觉符合 §5.1 锁定规范（暖白主、sage 仅点睛）。

研究分析台：
- [ ] 单轮追踪按 F1→F2→F3→F4 揭示，含输入/输出闭环。
- [ ] `boundary_flag=true` 候选显式标为「出局」，且 `weighted_total` 划除、不参与择优展示。
- [ ] 批量总览数字来自真实 run（非硬编码占位）。
- [ ] 框架对标三块完整，EPITOME 标注 IP limitation。

通用：
- [ ] MOCK/LIVE 经环境变量切换，LIVE 直连 FastAPI 无需改组件。
- [ ] 学生端与分析台可各自独立 build / 部署。
- [ ] 模块切换通过本地 transition 容器完成，尊重 reduced motion，且 `rg "scrollIntoView" frontend` 无匹配。

---

## 9. 不在本模块范围

- 不改后端 F1–F4 逻辑与 `/chat` / `/chat/stream` schema。
- 不在学生端做任何分析/打分展示。
- 不做跨会话画像/长期记忆的后端存储与删除接口；前端只维护本地会话历史清除能力。
- 鉴权 / 监护人知情机制属后续，本规格只要求分析台路由可加鉴权中间件。
