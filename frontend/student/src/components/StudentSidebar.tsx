import type { SessionRecord } from "../hooks/useStudentSessions";
import styles from "./StudentSidebar.module.css";

interface StudentSidebarProps {
  className?: string;
  currentId: string;
  sessions: SessionRecord[];
  onClearSessions: () => void;
  onClose?: () => void;
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
  className,
  currentId,
  sessions,
  onClearSessions,
  onClose,
  onNewSession,
  onSwitchSession,
}: StudentSidebarProps) {
  return (
    <aside className={`${styles.sidebar} ${className ?? ""}`} aria-label="会话列表">
      <div className={styles.header}>
        <div>
          <p>EmoAgent</p>
          <strong>学生空间</strong>
        </div>
        {onClose ? (
          <button className={styles.textButton} type="button" onClick={onClose}>
            关闭
          </button>
        ) : null}
      </div>

      <button className={styles.primaryButton} type="button" onClick={onNewSession}>
        新对话
      </button>

      <div className={styles.sessionList} aria-label="本地会话">
        {sessions.map((session) => {
          const active = session.id === currentId;

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
              <span className={styles.sessionTitle}>{session.title}</span>
              <span className={styles.sessionPreview}>{preview(session)}</span>
              <span className={styles.sessionTime}>
                {formatter.format(session.updatedAt)}
              </span>
            </button>
          );
        })}
      </div>

      <button className={styles.clearButton} type="button" onClick={onClearSessions}>
        清空本地记忆
      </button>
    </aside>
  );
}
