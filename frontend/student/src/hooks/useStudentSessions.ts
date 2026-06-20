import { useMemo, useRef, useState } from "react";

export interface StudentMessage {
  id: string;
  role: "student" | "agent";
  text: string;
  createdAt: number;
}

export interface SessionRecord {
  id: string;
  title: string;
  createdAt: number;
  updatedAt: number;
  messages: StudentMessage[];
}

const STORAGE_KEY = "emoagent.student.sessions.v1";
const CURRENT_ID_KEY = "emoagent.student.currentSessionId.v1";
const TAB_CURRENT_ID_KEY = "emoagent.student.tabCurrentSessionId.v1";
const ANONYMOUS_USER_ID_KEY = "emoagent.student.anonymousUserId.v1";
const DEFAULT_TITLE = "新的对话";
const TITLE_LIMIT = 20;

interface InitialSessionState {
  sessions: SessionRecord[];
  currentId: string;
}

function createId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }

  return `local-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

function clipTitle(text: string): string {
  const normalized = text.trim().replace(/\s+/g, " ");

  if (!normalized) {
    return DEFAULT_TITLE;
  }

  return normalized.length > TITLE_LIMIT
    ? `${normalized.slice(0, TITLE_LIMIT)}...`
    : normalized;
}

function createSession(now = Date.now()): SessionRecord {
  return {
    id: createId(),
    title: DEFAULT_TITLE,
    createdAt: now,
    updatedAt: now,
    messages: [],
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isFiniteTimestamp(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

function normalizeMessage(value: unknown): StudentMessage | null {
  if (!isRecord(value)) {
    return null;
  }

  const { id, role, text, createdAt } = value;

  if (
    typeof id !== "string" ||
    (role !== "student" && role !== "agent") ||
    typeof text !== "string" ||
    !isFiniteTimestamp(createdAt)
  ) {
    return null;
  }

  return {
    id,
    role,
    text,
    createdAt,
  };
}

function normalizeSession(value: unknown): SessionRecord | null {
  if (!isRecord(value)) {
    return null;
  }

  const { id, title, createdAt, updatedAt, messages } = value;

  if (
    typeof id !== "string" ||
    typeof title !== "string" ||
    !isFiniteTimestamp(createdAt) ||
    !isFiniteTimestamp(updatedAt) ||
    !Array.isArray(messages)
  ) {
    return null;
  }

  return {
    id,
    title,
    createdAt,
    updatedAt,
    messages: messages
      .map((message) => normalizeMessage(message))
      .filter((message): message is StudentMessage => message !== null),
  };
}

function readTabCurrentId(): string | null {
  if (typeof sessionStorage === "undefined") {
    return null;
  }

  try {
    return sessionStorage.getItem(TAB_CURRENT_ID_KEY);
  } catch {
    return null;
  }
}

function writeCurrentId(currentId: string): void {
  if (typeof localStorage !== "undefined") {
    localStorage.setItem(CURRENT_ID_KEY, currentId);
  }

  if (typeof sessionStorage !== "undefined") {
    try {
      sessionStorage.setItem(TAB_CURRENT_ID_KEY, currentId);
    } catch {
      // Ignore unavailable session storage; local history remains usable.
    }
  }
}

function clearTabCurrentId(): void {
  if (typeof sessionStorage === "undefined") {
    return;
  }

  try {
    sessionStorage.removeItem(TAB_CURRENT_ID_KEY);
  } catch {
    // Ignore unavailable session storage.
  }
}

function readInitialSessionState(): InitialSessionState {
  if (typeof localStorage === "undefined") {
    const session = createSession();
    return { sessions: [session], currentId: session.id };
  }

  const freshSession = createSession();

  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : null;

    if (Array.isArray(parsed) && parsed.length > 0) {
      const sessions = parsed
        .map((session) => normalizeSession(session))
        .filter((session): session is SessionRecord => session !== null);

      if (sessions.length > 0) {
        const tabCurrentId = readTabCurrentId();

        if (
          tabCurrentId &&
          sessions.some((session) => session.id === tabCurrentId)
        ) {
          writeCurrentId(tabCurrentId);
          return { sessions, currentId: tabCurrentId };
        }

        const previousSessions = sessions.filter(
          (session) => session.messages.length > 0,
        );
        const next = [freshSession, ...previousSessions];

        localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
        writeCurrentId(freshSession.id);
        return { sessions: next, currentId: freshSession.id };
      }
    }
  } catch {
    localStorage.removeItem(STORAGE_KEY);
    localStorage.removeItem(CURRENT_ID_KEY);
    clearTabCurrentId();
  }

  localStorage.setItem(STORAGE_KEY, JSON.stringify([freshSession]));
  writeCurrentId(freshSession.id);
  return { sessions: [freshSession], currentId: freshSession.id };
}

function readAnonymousUserId(): string {
  if (typeof localStorage === "undefined") {
    return createId();
  }

  const stored = localStorage.getItem(ANONYMOUS_USER_ID_KEY);
  if (stored) {
    return stored;
  }

  const id = createId();
  localStorage.setItem(ANONYMOUS_USER_ID_KEY, id);
  return id;
}

function persist(sessions: SessionRecord[], currentId: string): void {
  if (typeof localStorage === "undefined") {
    return;
  }

  localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
  writeCurrentId(currentId);
}

export function useStudentSessions() {
  const [initialSessionState] = useState<InitialSessionState>(() =>
    readInitialSessionState(),
  );
  const [sessions, setSessions] = useState<SessionRecord[]>(
    () => initialSessionState.sessions,
  );
  const [currentId, setCurrentId] = useState<string>(
    () => initialSessionState.currentId,
  );
  const [anonymousUserId, setAnonymousUserId] = useState<string>(() =>
    readAnonymousUserId(),
  );
  const sessionsRef = useRef(sessions);
  const currentIdRef = useRef(currentId);

  const currentSession = useMemo(
    () => sessions.find((session) => session.id === currentId) ?? sessions[0],
    [currentId, sessions],
  );

  function updateSessions(
    updater: (previous: SessionRecord[]) => SessionRecord[],
    nextCurrentId = currentIdRef.current,
  ): void {
    const next = updater(sessionsRef.current);

    sessionsRef.current = next;
    currentIdRef.current = nextCurrentId;
    setSessions(next);
    persist(next, nextCurrentId);
  }

  function appendMessage(
    role: StudentMessage["role"],
    text: string,
    sessionId = currentIdRef.current,
  ): StudentMessage | null {
    const targetSessionId = sessionId;

    if (!sessionsRef.current.some((session) => session.id === targetSessionId)) {
      return null;
    }

    const now = Date.now();
    const message: StudentMessage = {
      id: createId(),
      role,
      text,
      createdAt: now,
    };

    updateSessions((previous) =>
      previous.map((session) => {
        if (session.id !== targetSessionId) {
          return session;
        }

        const isFirstStudentMessage =
          role === "student" &&
          !session.messages.some((item) => item.role === "student");

        return {
          ...session,
          title: isFirstStudentMessage ? clipTitle(text) : session.title,
          updatedAt: now,
          messages: [...session.messages, message],
        };
      }),
    );

    return message;
  }

  function appendUserMessage(text: string, sessionId?: string): StudentMessage | null {
    return appendMessage("student", text, sessionId);
  }

  function appendAgentMessage(text: string, sessionId?: string): StudentMessage | null {
    return appendMessage("agent", text, sessionId);
  }

  function updateAgentMessage(
    messageId: string,
    text: string,
    sessionId = currentIdRef.current,
  ): void {
    updateSessions((previous) =>
      previous.map((session) => {
        if (session.id !== sessionId) {
          return session;
        }
        return {
          ...session,
          updatedAt: Date.now(),
          messages: session.messages.map((message) =>
            message.id === messageId && message.role === "agent"
              ? { ...message, text }
              : message,
          ),
        };
      }),
    );
  }

  function newSession(): SessionRecord {
    const session = createSession();

    setCurrentId(session.id);
    currentIdRef.current = session.id;
    updateSessions((previous) => [session, ...previous], session.id);

    return session;
  }

  function switchSession(sessionId: string): void {
    if (!sessions.some((session) => session.id === sessionId)) {
      return;
    }

    setCurrentId(sessionId);
    currentIdRef.current = sessionId;
    persist(sessions, sessionId);
  }

  function clearSessions(): void {
    const session = createSession();

    setCurrentId(session.id);
    setSessions([session]);
    currentIdRef.current = session.id;
    sessionsRef.current = [session];
    persist([session], session.id);
  }

  function resetAnonymousUserId(): string {
    const next = createId();
    setAnonymousUserId(next);
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(ANONYMOUS_USER_ID_KEY, next);
    }
    return next;
  }

  return {
    sessions,
    currentId,
    anonymousUserId,
    currentSession,
    appendUserMessage,
    appendAgentMessage,
    updateAgentMessage,
    newSession,
    switchSession,
    clearSessions,
    resetAnonymousUserId,
  };
}
