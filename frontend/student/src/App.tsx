import { useEffect, useRef, useState } from "react";
import styles from "./App.module.css";
import { BreathingPanel } from "./components/BreathingPanel";
import { Composer } from "./components/Composer";
import { MessageList } from "./components/MessageList";
import { RecordManagementPanel } from "./components/RecordManagementPanel";
import { ReferralPanel } from "./components/ReferralPanel";
import { StarterPrompts } from "./components/StarterPrompts";
import {
  StudentSidebar,
  type StudentMainView,
} from "./components/StudentSidebar";
import { TransitionSlot } from "./components/TransitionSlot";
import { clearAnonymousMemory } from "@emoedu/shared";
import { useStudentChat } from "./hooks/useStudentChat";
import { useStudentSessions } from "./hooks/useStudentSessions";

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [activeView, setActiveView] = useState<StudentMainView>("chat");
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const {
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
  } = useStudentSessions();
  const { loading, riskLevel, referralLocked, send, resetReferral } =
    useStudentChat(currentId, anonymousUserId);
  const activeSessionIdRef = useRef(currentId);

  const messages = currentSession?.messages ?? [];
  const hasMessages = messages.length > 0;

  useEffect(() => {
    activeSessionIdRef.current = currentId;
  }, [currentId]);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [currentSession?.messages.length, activeView]);

  async function handleSend(text: string) {
    const trimmed = text.trim();

    if (!trimmed || loading || referralLocked) {
      return;
    }

    const targetSessionId = currentId;
    appendUserMessage(trimmed, targetSessionId);
    const agentMessage = appendAgentMessage("", targetSessionId);
    let streamedText = "";
    const view = await send(trimmed, {
      isCurrent: () => activeSessionIdRef.current === targetSessionId,
      onDelta: (delta) => {
        streamedText += delta;
        if (agentMessage) {
          updateAgentMessage(agentMessage.id, streamedText, targetSessionId);
        }
      },
    });
    if (agentMessage) {
      updateAgentMessage(agentMessage.id, view.reply_text, targetSessionId);
    } else {
      appendAgentMessage(view.reply_text, targetSessionId);
    }
  }

  function handlePrompt(label: string) {
    void handleSend(label);
  }

  function handleNewSession() {
    activeSessionIdRef.current = "";
    const session = newSession();
    activeSessionIdRef.current = session.id;
    resetReferral();
    setActiveView("chat");
    setSidebarOpen(false);
  }

  async function handleClearSessions() {
    activeSessionIdRef.current = "";
    await clearAnonymousMemory(anonymousUserId).catch(() => undefined);
    clearSessions();
    resetAnonymousUserId();
    resetReferral();
    setSidebarOpen(false);
  }

  function handleOpenBreathing() {
    setActiveView("breathing");
    setSidebarOpen(false);
  }

  function handleOpenRecords() {
    setActiveView("records");
    setSidebarOpen(false);
  }

  function handleSwitchSession(sessionId: string) {
    if (!sessions.some((session) => session.id === sessionId)) {
      return;
    }

    activeSessionIdRef.current = sessionId;
    switchSession(sessionId);
    setActiveView("chat");
    setSidebarOpen(false);
  }

  const sidebar = (
    <StudentSidebar
      activeView={activeView}
      currentId={currentId}
      sessions={sessions}
      onOpenBreathing={handleOpenBreathing}
      onOpenRecords={handleOpenRecords}
      onNewSession={handleNewSession}
      onSwitchSession={handleSwitchSession}
    />
  );

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
            activeView={activeView}
            className={styles.mobileSidebar}
            currentId={currentId}
            sessions={sessions}
            onClose={() => setSidebarOpen(false)}
            onOpenBreathing={handleOpenBreathing}
            onOpenRecords={handleOpenRecords}
            onNewSession={handleNewSession}
            onSwitchSession={handleSwitchSession}
          />
        </div>
      ) : null}

      <div className={styles.shell}>
        <div className={styles.desktopSidebar}>{sidebar}</div>

        <main className={styles.chatColumn}>
          <header className={styles.topBar}>
            <p>你可以慢慢说，我会认真听</p>
          </header>

          <TransitionSlot viewKey={activeView} className={styles.mainTransition}>
            {activeView === "chat" ? (
              <>
              <div className={styles.chatScroll} ref={scrollRef}>
                {hasMessages ? (
                  <MessageList messages={messages} />
                ) : (
                  <section className={styles.openingState} aria-label="开始对话">
                    <div className={styles.openingLabel}>
                      <span className={styles.openingDot} />
                      <strong>EmoAgent</strong>
                    </div>
                    <p className={styles.openingText}>
                      嗨，我在这儿。今天有什么想说的，随便聊聊就好，不用着急。
                    </p>
                  </section>
                )}
              </div>

              <div className={styles.composerArea}>
                {!hasMessages && !referralLocked ? (
                  <StarterPrompts disabled={loading} onPick={handlePrompt} />
                ) : null}
                {referralLocked ? (
                  <ReferralPanel riskLevel={riskLevel} />
                ) : (
                  <Composer disabled={loading} loading={loading} onSend={handleSend} />
                )}
              </div>
              </>
            ) : (
            <section className={styles.toolView} aria-label="辅助视图">
              {activeView === "records" ? (
                <RecordManagementPanel
                  sessions={sessions}
                  onClearSessions={handleClearSessions}
                />
              ) : null}
              {activeView === "breathing" ? <BreathingPanel /> : null}
              </section>
            )}
          </TransitionSlot>
        </main>
      </div>
    </div>
  );
}
