import { FormEvent, KeyboardEvent, useState } from "react";
import styles from "./Composer.module.css";

interface ComposerProps {
  disabled?: boolean;
  loading?: boolean;
  onSend: (text: string) => void;
}

export function Composer({
  disabled = false,
  loading = false,
  onSend,
}: ComposerProps) {
  const [value, setValue] = useState("");
  const hasSendableText = value.trim().length > 0;
  const canSend = hasSendableText && !disabled && !loading;
  const sendButtonClassName = canSend
    ? `${styles.sendButton} ${styles.sendButtonReady}`
    : styles.sendButton;

  function submit() {
    const text = value.trim();

    if (!text || disabled || loading) {
      return;
    }

    setValue("");
    onSend(text);
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submit();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form className={styles.composer} onSubmit={handleSubmit}>
      <textarea
        aria-label="输入消息"
        className={styles.input}
        disabled={disabled || loading}
        rows={1}
        value={value}
        placeholder="想说点什么..."
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button
        aria-label={loading ? "正在回应" : "发送"}
        className={sendButtonClassName}
        data-send-ready={String(canSend)}
        disabled={!canSend}
        type="submit"
      >
        {loading ? (
          <span aria-hidden="true">...</span>
        ) : (
          <svg
            aria-hidden="true"
            className={styles.sendIcon}
            fill="none"
            viewBox="0 0 24 24"
          >
            <path
              d="M12 19V5m0 0-5.25 5.25M12 5l5.25 5.25"
              stroke="currentColor"
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="3.2"
            />
          </svg>
        )}
      </button>
    </form>
  );
}
