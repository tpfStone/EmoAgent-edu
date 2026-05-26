import type { SessionRecord } from "../hooks/useStudentSessions";
import styles from "./StudentSidebar.module.css";

export type StudentMainView = "chat" | "memory" | "breathing";

interface StudentSidebarProps {
  activeView: StudentMainView;
  className?: string;
  currentId: string;
  sessions: SessionRecord[];
  onClose?: () => void;
  onOpenBreathing: () => void;
  onOpenMemory: () => void;
  onNewSession: () => void;
  onSwitchSession: (sessionId: string) => void;
}

const formatter = new Intl.DateTimeFormat("zh-CN", {
  month: "2-digit",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

function preview(session: SessionRecord): string {
  const latest = session.messages.at(-1);

  if (!latest) {
    return "还没有消息";
  }

  return latest.text.replace(/\s+/g, " ").trim();
}

export function StudentSidebar({
  activeView,
  className,
  currentId,
  sessions,
  onClose,
  onOpenBreathing,
  onOpenMemory,
  onNewSession,
  onSwitchSession,
}: StudentSidebarProps) {
  return (
    <aside className={`${styles.sidebar} ${className ?? ""}`} aria-label="会话列表">
      <div className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandDot} />
          <strong>EmoAgent</strong>
        </div>
        {onClose ? (
          <button className={styles.textButton} type="button" onClick={onClose}>
            关闭
          </button>
        ) : null}
      </div>

      <button className={styles.primaryButton} type="button" onClick={onNewSession}>
        <span aria-hidden="true">+</span>
        开启新的对话
      </button>

      <div className={styles.sectionLabel}>最近聊过</div>

      <div className={styles.sessionList} aria-label="本地会话">
        {sessions.map((session, index) => {
          const active = activeView === "chat" && session.id === currentId;

          return (
            <button
              className={`${styles.sessionButton} ${
                active ? styles.sessionButtonActive : ""
              }`}
              key={session.id}
              type="button"
              aria-current={active ? "true" : undefined}
              onClick={() => onSwitchSession(session.id)}
            >
              <span className={`${styles.sessionDot} ${styles[`dot${index % 4}`]}`} />
              <span className={styles.sessionTitle}>{session.title}</span>
              <span className={styles.sessionTime}>
                {session.messages.length > 0
                  ? formatter.format(session.updatedAt)
                  : preview(session)}
              </span>
            </button>
          );
        })}
      </div>

      <nav className={styles.toolList} aria-label="学生工具">
        <button
          className={`${styles.toolButton} ${
            activeView === "memory" ? styles.toolButtonActive : ""
          }`}
          type="button"
          onClick={onOpenMemory}
        >
          <span className={styles.toolDot} />
          <span>我的情绪轨迹</span>
        </button>
        <button
          className={`${styles.toolButton} ${
            activeView === "breathing" ? styles.toolButtonActive : ""
          }`}
          type="button"
          onClick={onOpenBreathing}
        >
          <span className={styles.toolRing} />
          <span>静一静 · 呼吸</span>
        </button>
      </nav>
    </aside>
  );
}
