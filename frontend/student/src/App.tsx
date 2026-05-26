import { useEffect, useRef, useState } from "react";
import styles from "./App.module.css";
import { BreathingPanel } from "./components/BreathingPanel";
import { Composer } from "./components/Composer";
import { EmotionMemoryPanel } from "./components/EmotionMemoryPanel";
import { MessageList } from "./components/MessageList";
import { ReferralPanel } from "./components/ReferralPanel";
import { StarterPrompts } from "./components/StarterPrompts";
import { StudentSidebar } from "./components/StudentSidebar";
import { useStudentChat } from "./hooks/useStudentChat";
import { useStudentSessions } from "./hooks/useStudentSessions";

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [breathingOpen, setBreathingOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const {
    sessions,
    currentId,
    currentSession,
    appendUserMessage,
    appendAgentMessage,
    newSession,
    switchSession,
    clearSessions,
  } = useStudentSessions();
  const { loading, riskLevel, referralLocked, send, resetReferral } =
    useStudentChat(currentId);
  const activeSessionIdRef = useRef(currentId);

  const messages = currentSession?.messages ?? [];
  const hasMessages = messages.length > 0;

  useEffect(() => {
    activeSessionIdRef.current = currentId;
  }, [currentId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [currentSession?.messages.length]);

  async function handleSend(text: string) {
    const trimmed = text.trim();

    if (!trimmed || loading || referralLocked) {
      return;
    }

    const targetSessionId = currentId;
    appendUserMessage(trimmed, targetSessionId);
    const view = await send(trimmed, {
      isCurrent: () => activeSessionIdRef.current === targetSessionId,
    });
    appendAgentMessage(view.reply_text, targetSessionId);
  }

  function handlePrompt(label: string) {
    void handleSend(label);
  }

  function handleNewSession() {
    activeSessionIdRef.current = "";
    const session = newSession();
    activeSessionIdRef.current = session.id;
    resetReferral();
    setSidebarOpen(false);
  }

  function handleClearSessions() {
    activeSessionIdRef.current = "";
    clearSessions();
    resetReferral();
    setSidebarOpen(false);
  }

  function handleSwitchSession(sessionId: string) {
    if (!sessions.some((session) => session.id === sessionId)) {
      return;
    }

    activeSessionIdRef.current = sessionId;
    switchSession(sessionId);
    setSidebarOpen(false);
  }

  return (
    <div className={styles.app}>
      <button
        className={styles.mobileMenuButton}
        type="button"
        onClick={() => setSidebarOpen(true)}
      >
        会话
      </button>

      {sidebarOpen ? (
        <div className={styles.drawerLayer} role="presentation">
          <button
            className={styles.drawerBackdrop}
            type="button"
            aria-label="关闭会话列表"
            onClick={() => setSidebarOpen(false)}
          />
          <StudentSidebar
            className={styles.mobileSidebar}
            currentId={currentId}
            sessions={sessions}
            onClearSessions={handleClearSessions}
            onClose={() => setSidebarOpen(false)}
            onNewSession={handleNewSession}
            onSwitchSession={handleSwitchSession}
          />
        </div>
      ) : null}

      <div className={styles.shell}>
        <StudentSidebar
          className={styles.desktopSidebar}
          currentId={currentId}
          sessions={sessions}
          onClearSessions={handleClearSessions}
          onNewSession={handleNewSession}
          onSwitchSession={handleSwitchSession}
        />

        <main className={styles.chatColumn}>
          <header className={styles.topBar}>
            <div className={styles.sessionMeta}>
              <span>学生对话</span>
              <strong>{currentSession?.title ?? "新的对话"}</strong>
            </div>
            <div className={styles.utilityControls} aria-label="辅助工具">
              <button
                className={`${styles.utilityButton} ${
                  memoryOpen ? styles.utilityButtonActive : ""
                }`}
                type="button"
                onClick={() => setMemoryOpen((open) => !open)}
              >
                情绪轨迹
              </button>
              <button
                className={`${styles.utilityButton} ${
                  breathingOpen ? styles.utilityButtonActive : ""
                }`}
                type="button"
                onClick={() => setBreathingOpen((open) => !open)}
              >
                呼吸
              </button>
            </div>
          </header>

          {(memoryOpen || breathingOpen) && (
            <div className={styles.mobilePanels}>
              {memoryOpen ? (
                <EmotionMemoryPanel
                  sessions={sessions}
                  onClearSessions={handleClearSessions}
                />
              ) : null}
              {breathingOpen ? <BreathingPanel /> : null}
            </div>
          )}

          <div className={styles.chatScroll} ref={scrollRef}>
            {hasMessages ? (
              <MessageList messages={messages} />
            ) : (
              <section className={styles.emptyState} aria-label="开始对话">
                <BreathingPanel variant="inline" />
                <div className={styles.emptyCopy}>
                  <h1>我在这里听你说</h1>
                  <p>可以从一句很小的话开始，不需要整理好再说。</p>
                </div>
                <StarterPrompts disabled={loading} onPick={handlePrompt} />
              </section>
            )}
          </div>

          <div className={styles.composerArea}>
            {referralLocked ? (
              <ReferralPanel riskLevel={riskLevel} />
            ) : (
              <Composer disabled={loading} loading={loading} onSend={handleSend} />
            )}
          </div>
        </main>

        <aside className={styles.sidePanels} aria-label="辅助面板">
          {memoryOpen ? (
            <EmotionMemoryPanel
              sessions={sessions}
              onClearSessions={handleClearSessions}
            />
          ) : null}
          {breathingOpen ? <BreathingPanel /> : null}
        </aside>
      </div>
    </div>
  );
}
