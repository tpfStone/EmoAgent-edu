import { MOCK_SAMPLES, getSampleById } from "./samples";
import type { ChatRequest, FullChatResponse, StudentChatView } from "./types";

const env =
  ((import.meta as unknown as { env?: Record<string, string | undefined> }).env ??
    {});

const mode = env.VITE_API_MODE ?? "mock";
const baseUrl =
  env.VITE_API_BASE ?? env.VITE_API_BASE_URL ?? env.VITE_EMOEDU_API_BASE_URL ?? "";

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
  return `${baseUrl.replace(/\/$/, "")}/chat`;
}

export async function fetchChat(request: ChatRequest): Promise<FullChatResponse> {
  if (mode === "mock") {
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

export async function fetchStudentChat(
  request: ChatRequest,
): Promise<StudentChatView> {
  const response = await fetchChat(request);

  // Transport still uses /chat; the returned public value is narrowed here.
  return {
    session_id: response.session_id,
    reply_text: response.reply_text,
    risk_level: response.risk_level,
  };
}
