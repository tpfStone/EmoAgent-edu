import { MOCK_SAMPLES, getSampleById } from "./samples";
import type {
  ChatRequest,
  ChatStreamEvent,
  CriticGuidanceStatusResponse,
  FullChatResponse,
  StudentChatView,
} from "./types";

function getEnv(): Record<string, string | undefined> {
  const viteEnv =
    (import.meta as unknown as { env?: Record<string, string | undefined> }).env ??
    {};
  const processEnv =
    (
      globalThis as typeof globalThis & {
        process?: { env?: Record<string, string | undefined> };
      }
    ).process?.env ?? {};
  return { ...processEnv, ...viteEnv };
}

function getMode(): string {
  return getEnv().VITE_API_MODE ?? "mock";
}

function getBaseUrl(): string {
  const env = getEnv();
  return env.VITE_API_BASE ?? env.VITE_API_BASE_URL ?? env.VITE_EMOEDU_API_BASE_URL ?? "";
}

const MOCK_STREAM_START_DELAY_MS = 520;
const MOCK_STREAM_CHUNK_DELAY_MS = 28;

function delay(ms: number): Promise<void> {
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
  });
}

// Mock-only demo routing. Real crisis classification stays in backend F1.
const CRISIS_KEYWORDS = [
  "不想活",
  "不想存在",
  "消失",
  "结束这一切",
  "活着没意思",
  "自杀",
  "自残",
];

const MESSAGE_HINTS: Record<string, string[]> = {
  syn_0007: ["作业", "考试", "压力", "学业"],
  syn_0021: ["同学", "朋友", "排挤", "嘲笑"],
  syn_0032: ["家里", "父母", "爸妈", "沟通"],
  crisis: CRISIS_KEYWORDS,
};

function containsAny(value: string, terms: string[]): boolean {
  return terms.some((term) => value.includes(term));
}

function getMockResponse(request: ChatRequest): FullChatResponse | undefined {
  if (containsAny(request.current_message, CRISIS_KEYWORDS)) {
    return getSampleById("crisis");
  }

  const bySessionId = MOCK_SAMPLES.find((sample) =>
    request.session_id.includes(sample.session_id),
  );

  if (bySessionId) {
    return bySessionId;
  }

  return MOCK_SAMPLES.find((sample) =>
    containsAny(request.current_message, MESSAGE_HINTS[sample.session_id] ?? []),
  );
}

function buildChatUrl(): string {
  return `${getBaseUrl().replace(/\/$/, "")}/chat`;
}

function buildChatStreamUrl(): string {
  return `${getBaseUrl().replace(/\/$/, "")}/chat/stream`;
}

function buildMemoryUrl(anonymousUserId: string): string {
  const baseUrl = getBaseUrl();
  const root =
    baseUrl.replace(/\/$/, "") ||
    (typeof window !== "undefined" ? window.location.origin : "http://localhost");
  const url = new URL(`${root}/api/memory`);
  url.searchParams.set("anonymous_user_id", anonymousUserId);
  return url.toString();
}

function buildCriticGuidanceUrl(sessionId: string): string {
  return `${getBaseUrl().replace(/\/$/, "")}/api/critic/guidance/${encodeURIComponent(sessionId)}`;
}

export async function fetchChat(request: ChatRequest): Promise<FullChatResponse> {
  if (getMode() === "mock") {
    return getMockResponse(request) ?? MOCK_SAMPLES[0];
  }

  const response = await fetch(buildChatUrl(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed with status ${response.status}`);
  }

  return (await response.json()) as FullChatResponse;
}

export async function fetchCriticGuidance(
  sessionId: string,
): Promise<CriticGuidanceStatusResponse> {
  if (getMode() === "mock") {
    const sample = getSampleById(sessionId);
    return {
      session_id: sessionId,
      status: "ready",
      guidance: "Mock guidance uses the bundled sample scores.",
      scores: sample?.scores ?? [],
      error: "",
      updated_at: null,
    };
  }

  const response = await fetch(buildCriticGuidanceUrl(sessionId));

  if (!response.ok) {
    throw new Error(`Critic guidance request failed with status ${response.status}`);
  }

  return (await response.json()) as CriticGuidanceStatusResponse;
}

export interface StreamChatOptions {
  onEvent?: (event: ChatStreamEvent) => void;
  onDelta?: (text: string) => void;
}

export async function fetchStudentChatStream(
  request: ChatRequest,
  options: StreamChatOptions = {},
): Promise<StudentChatView> {
  if (getMode() === "mock") {
    const response = getMockResponse(request) ?? MOCK_SAMPLES[0];
    const view = toStudentView(response, request.anonymous_user_id ?? null);
    const { reply_text: _replyText, ...metadata } = response;
    options.onEvent?.({ event: "metadata", data: metadata });
    await delay(MOCK_STREAM_START_DELAY_MS);
    for (let index = 0; index < response.reply_text.length; index += 2) {
      const text = response.reply_text.slice(index, index + 2);
      options.onDelta?.(text);
      options.onEvent?.({ event: "delta", data: { text } });
      await delay(MOCK_STREAM_CHUNK_DELAY_MS);
    }
    options.onEvent?.({ event: "done", data: { ...response, anonymous_user_id: view.anonymous_user_id ?? null } });
    return view;
  }

  const response = await fetch(buildChatStreamUrl(), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    throw new Error(`Chat stream failed with status ${response.status}`);
  }
  if (!response.body) {
    throw new Error("Chat stream response body is empty");
  }

  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  let buffer = "";
  let finalResponse: FullChatResponse | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split(/\n\n/);
    buffer = events.pop() ?? "";
    for (const rawEvent of events) {
      const parsed = parseSseEvent(rawEvent);
      if (!parsed) continue;
      options.onEvent?.(parsed);
      if (parsed.event === "delta") {
        options.onDelta?.(parsed.data.text);
      }
      if (parsed.event === "done") {
        finalResponse = parsed.data;
      }
      if (parsed.event === "error") {
        throw new Error(parsed.data.message);
      }
    }
  }

  if (!finalResponse) {
    throw new Error("Chat stream ended before done event");
  }

  return toStudentView(finalResponse, request.anonymous_user_id ?? null);
}

export async function fetchStudentChat(
  request: ChatRequest,
): Promise<StudentChatView> {
  const response = await fetchChat(request);

  // Transport still uses /chat; the returned public value is narrowed here.
  return toStudentView(response, request.anonymous_user_id ?? null);
}

export async function clearAnonymousMemory(anonymousUserId: string): Promise<void> {
  if (getMode() === "mock" || !anonymousUserId) {
    return;
  }
  const response = await fetch(buildMemoryUrl(anonymousUserId), {
    method: "DELETE",
  });
  if (!response.ok) {
    throw new Error(`Memory delete failed with status ${response.status}`);
  }
}

function toStudentView(
  response: FullChatResponse,
  fallbackAnonymousUserId: string | null,
): StudentChatView {
  return {
    session_id: response.session_id,
    anonymous_user_id: response.anonymous_user_id ?? fallbackAnonymousUserId,
    reply_text: response.reply_text,
    risk_level: response.risk_level,
  };
}

function parseSseEvent(raw: string): ChatStreamEvent | null {
  const lines = raw.split(/\n/);
  const eventLine = lines.find((line) => line.startsWith("event:"));
  const dataLine = lines.find((line) => line.startsWith("data:"));
  if (!eventLine || !dataLine) return null;
  const event = eventLine.slice("event:".length).trim();
  const data = JSON.parse(dataLine.slice("data:".length).trim());
  return { event, data } as ChatStreamEvent;
}
