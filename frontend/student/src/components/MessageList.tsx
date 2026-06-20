import type { StudentMessage } from "../hooks/useStudentSessions";
import styles from "./MessageList.module.css";

interface MessageListProps {
  loading?: boolean;
  messages: StudentMessage[];
}

function paragraphs(text: string): string[] {
  return text
    .split(/\n+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function MessageList({ loading = false, messages }: MessageListProps) {
  return (
    <div className={styles.messageList} aria-live="polite">
      {messages.map((message, index) => {
        const isPendingAgent =
          loading &&
          index === messages.length - 1 &&
          message.role === "agent" &&
          message.text.trim().length === 0;

        return message.role === "agent" ? (
          <article
            aria-label={isPendingAgent ? "EmoAgent 正在回应" : undefined}
            className={
              isPendingAgent
                ? `${styles.agentMessage} ${styles.pendingAgentMessage}`
                : styles.agentMessage
            }
            key={message.id}
          >
            <div
              className={
                isPendingAgent
                  ? `${styles.agentLabel} ${styles.pendingAgentLabel}`
                  : styles.agentLabel
              }
            >
              <span className={styles.agentDot} />
              <span>EmoAgent</span>
            </div>
            {isPendingAgent ? (
              <div className={styles.typingIndicator} aria-hidden="true">
                <span />
                <span />
                <span />
              </div>
            ) : (
              <div className={styles.agentText}>
                {paragraphs(message.text).map((paragraph, paragraphIndex) => (
                  <p key={`${message.id}-${paragraphIndex}`}>{paragraph}</p>
                ))}
              </div>
            )}
          </article>
        ) : (
          <article className={styles.studentRow} key={message.id}>
            <p className={styles.studentMessage}>{message.text}</p>
          </article>
        );
      })}
    </div>
  );
}
