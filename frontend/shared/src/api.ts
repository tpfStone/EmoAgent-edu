// ============================================================
// EmoEdu API 层
// 规格参考: docs/frontend/frontend-cc-spec.md §7
// ============================================================
import type { ChatRequest, FullChatResponse, StudentChatView } from './types'
import { MOCK_SAMPLES } from './samples'

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const _env: Record<string, string> = (import.meta as any)?.env ?? {}
const MODE: string = _env.VITE_API_MODE ?? 'mock'
const BASE: string = _env.VITE_API_BASE ?? ''

// ----------------------------------------------------------------
// Mock resolver — 从 samples.ts 返回匹配的样例，或默认第一条
// ----------------------------------------------------------------
function mockResolve(req: ChatRequest): Promise<FullChatResponse> {
  // 尝试按 session_id 前缀匹配 sample ID
  const matched = MOCK_SAMPLES.find(
    (s) =>
      req.session_id.includes(s.id) ||
      req.current_message.includes(s.input.slice(0, 8))
  )
  const sample = matched ?? MOCK_SAMPLES[0]
  // 注入实际的 session_id
  const resp: FullChatResponse = {
    ...sample.response,
    session_id: req.session_id,
  }
  // 模拟网络延迟
  return new Promise((resolve) => setTimeout(() => resolve(resp), 600))
}

// ----------------------------------------------------------------
// 全量请求 — 供研究分析台使用
// ----------------------------------------------------------------
export async function fetchChat(req: ChatRequest): Promise<FullChatResponse> {
  if (MODE === 'mock') return mockResolve(req)

  const r = await fetch(`${BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!r.ok) throw new Error(`POST /chat → ${r.status}`)
  return r.json() as Promise<FullChatResponse>
}

// ----------------------------------------------------------------
// 学生端专用包装 — 函数签名层切断
// 内部完成 Pick，返回值类型只含三字段
// ----------------------------------------------------------------
export async function fetchChatStudent(
  req: ChatRequest
): Promise<StudentChatView> {
  const full = await fetchChat(req)
  // 仅取铁律三字段，其余字段在此丢弃
  const { session_id, reply_text, risk_level } = full
  return { session_id, reply_text, risk_level }
}
