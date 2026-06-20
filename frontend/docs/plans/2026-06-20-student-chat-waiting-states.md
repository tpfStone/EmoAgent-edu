# Student Chat Waiting States Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a calm waiting indicator for pending EmoAgent replies and make the send button visibly active as soon as the student enters sendable text.

**Architecture:** Keep the behavior local to the student chat UI. `App` passes the existing per-session `loading` state into `MessageList`; `MessageList` renders a pending state only for the last empty agent message; `Composer` derives a send-ready state from textarea content and existing disabled/loading flags.

**Tech Stack:** React 18, TypeScript, CSS Modules, Vitest, Testing Library, Vite, pnpm workspace.

---

## File Structure

- Modify `frontend/student/src/App.tsx`: pass `loading` to `MessageList` and keep the chat scrolled to the latest streamed text.
- Modify `frontend/student/src/components/MessageList.tsx`: add `loading` prop and render a pending reply indicator for the last empty agent message.
- Modify `frontend/student/src/components/MessageList.module.css`: add breathing label and typing dots animations with reduced-motion fallback.
- Modify `frontend/student/src/components/Composer.tsx`: derive `canSend`, add an observable ready state to the submit button, and preserve submit guards.
- Modify `frontend/student/src/components/Composer.module.css`: style ready, hover, focus, disabled, and loading-compatible button states.
- Create `frontend/student/src/App.waiting-state.test.tsx`: integration test for pending reply indicator disappearing after streamed text arrives.
- Create `frontend/student/src/components/Composer.test.tsx`: component test for send-ready button state.

### Task 1: Pending EmoAgent Reply State

**Files:**
- Create: `frontend/student/src/App.waiting-state.test.tsx`
- Modify: `frontend/student/src/App.tsx`
- Modify: `frontend/student/src/components/MessageList.tsx`
- Modify: `frontend/student/src/components/MessageList.module.css`

- [ ] **Step 1: Write the failing integration test**

Create `frontend/student/src/App.waiting-state.test.tsx`:

```tsx
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchStudentChatStream } from "@emoedu/shared";
import App from "./App";

vi.mock("@emoedu/shared", () => ({
  clearAnonymousMemory: vi.fn().mockResolvedValue(undefined),
  fetchStudentChatStream: vi.fn(),
}));

const fetchStudentChatStreamMock = vi.mocked(fetchStudentChatStream);

describe("student chat waiting state", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("shows a pending EmoAgent indicator until streamed text arrives", async () => {
    let onDelta: ((text: string) => void) | undefined;
    let resolveChat:
      | ((value: { session_id: string; reply_text: string; risk_level: "green" }) => void)
      | undefined;

    fetchStudentChatStreamMock.mockImplementation(async (_request, options) => {
      onDelta = options?.onDelta;
      return new Promise((resolve) => {
        resolveChat = resolve;
      });
    });

    render(<App />);

    const input = screen.getByRole("textbox", { name: "杈撳叆娑堟伅" });
    fireEvent.change(input, { target: { value: "hello" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(await screen.findByLabelText("EmoAgent 正在回应")).toBeTruthy();

    onDelta?.("streamed reply");
    resolveChat?.({
      session_id: "student-session",
      reply_text: "streamed reply",
      risk_level: "green",
    });

    await waitFor(() => {
      expect(screen.queryByLabelText("EmoAgent 正在回应")).toBeNull();
    });
    expect(screen.getByText("streamed reply")).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pnpm --filter @emoedu/student test -- App.waiting-state.test.tsx
```

Expected: FAIL because `EmoAgent 正在回应` is not rendered yet.

- [ ] **Step 3: Implement pending state wiring in `App.tsx`**

Change the messages and scroll section in `frontend/student/src/App.tsx`:

```tsx
  const messages = currentSession?.messages ?? [];
  const lastMessageText = messages[messages.length - 1]?.text ?? "";
```

Change the scroll effect dependencies:

```tsx
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [currentSession?.messages.length, lastMessageText, activeView]);
```

Pass loading to `MessageList`:

```tsx
                  <MessageList loading={loading} messages={messages} />
```

- [ ] **Step 4: Implement pending state rendering in `MessageList.tsx`**

Update `frontend/student/src/components/MessageList.tsx`:

```tsx
interface MessageListProps {
  loading?: boolean;
  messages: StudentMessage[];
}
```

Change the component signature and agent branch:

```tsx
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
```

- [ ] **Step 5: Add pending state CSS**

Append to `frontend/student/src/components/MessageList.module.css` before the media query:

```css
.pendingAgentMessage {
  min-height: 4.35rem;
}

.pendingAgentLabel {
  animation: agentBreath 1.6s var(--ease) infinite;
}

.pendingAgentLabel .agentDot {
  animation: agentDotPulse 1.6s var(--ease) infinite;
}

.typingIndicator {
  display: inline-flex;
  align-items: center;
  min-height: 2.4rem;
  gap: 0.38rem;
  padding-top: 0.08rem;
}

.typingIndicator span {
  width: 0.42rem;
  height: 0.42rem;
  border-radius: 50%;
  background: var(--sage);
  opacity: 0.48;
  animation: typingBounce 1.2s var(--ease) infinite;
}

.typingIndicator span:nth-child(2) {
  animation-delay: 120ms;
}

.typingIndicator span:nth-child(3) {
  animation-delay: 240ms;
}

@keyframes agentBreath {
  0%,
  100% {
    opacity: 0.58;
  }

  50% {
    opacity: 1;
  }
}

@keyframes agentDotPulse {
  0%,
  100% {
    box-shadow: 0 0 0 rgba(111, 156, 128, 0);
    transform: scale(0.92);
  }

  50% {
    box-shadow: 0 0 0 0.28rem rgba(111, 156, 128, 0.12);
    transform: scale(1);
  }
}

@keyframes typingBounce {
  0%,
  100% {
    opacity: 0.42;
    transform: translateY(0);
  }

  50% {
    opacity: 1;
    transform: translateY(-0.22rem);
  }
}

@media (prefers-reduced-motion: reduce) {
  .pendingAgentLabel,
  .pendingAgentLabel .agentDot,
  .typingIndicator span {
    animation: none;
    opacity: 1;
    transform: none;
  }
}
```

- [ ] **Step 6: Run test to verify it passes**

Run:

```bash
pnpm --filter @emoedu/student test -- App.waiting-state.test.tsx
```

Expected: PASS.

- [ ] **Step 7: Commit task 1**

```bash
git add frontend/student/src/App.tsx frontend/student/src/components/MessageList.tsx frontend/student/src/components/MessageList.module.css frontend/student/src/App.waiting-state.test.tsx
git commit -m "feat: show pending student chat reply"
```

### Task 2: Send Button Ready State

**Files:**
- Create: `frontend/student/src/components/Composer.test.tsx`
- Modify: `frontend/student/src/components/Composer.tsx`
- Modify: `frontend/student/src/components/Composer.module.css`

- [ ] **Step 1: Write the failing component test**

Create `frontend/student/src/components/Composer.test.tsx`:

```tsx
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";

describe("Composer", () => {
  afterEach(() => {
    cleanup();
  });

  it("marks the send button ready only when text can be sent", () => {
    render(<Composer onSend={vi.fn()} />);

    const input = screen.getByRole("textbox", { name: "杈撳叆娑堟伅" });
    const sendButton = screen.getByRole("button", { name: "鍙戦€?" });

    expect(sendButton).toBeDisabled();
    expect(sendButton).toHaveAttribute("data-send-ready", "false");

    fireEvent.change(input, { target: { value: "hello" } });

    expect(sendButton).not.toBeDisabled();
    expect(sendButton).toHaveAttribute("data-send-ready", "true");
  });

  it("does not mark the send button ready while loading", () => {
    render(<Composer loading={true} onSend={vi.fn()} />);

    const input = screen.getByRole("textbox", { name: "杈撳叆娑堟伅" });
    const sendButton = screen.getByRole("button", { name: "姝ｅ湪鍥炲簲" });

    fireEvent.change(input, { target: { value: "hello" } });

    expect(sendButton).toBeDisabled();
    expect(sendButton).toHaveAttribute("data-send-ready", "false");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
pnpm --filter @emoedu/student test -- Composer.test.tsx
```

Expected: FAIL because `data-send-ready` is not present yet.

- [ ] **Step 3: Implement send-ready state in `Composer.tsx`**

Update `frontend/student/src/components/Composer.tsx`:

```tsx
  const [value, setValue] = useState("");
  const hasSendableText = value.trim().length > 0;
  const canSend = hasSendableText && !disabled && !loading;
  const sendButtonClassName = canSend
    ? `${styles.sendButton} ${styles.sendButtonReady}`
    : styles.sendButton;
```

Update the button:

```tsx
      <button
        aria-label={loading ? "姝ｅ湪鍥炲簲" : "鍙戦€?"}
        className={sendButtonClassName}
        data-send-ready={String(canSend)}
        disabled={!canSend}
        type="submit"
      >
```

The existing `submit()` guard remains:

```tsx
    if (!text || disabled || loading) {
      return;
    }
```

- [ ] **Step 4: Implement send-ready CSS**

Update `frontend/student/src/components/Composer.module.css`:

```css
.sendButton {
  display: grid;
  width: 3.72rem;
  height: 3.72rem;
  flex: 0 0 auto;
  place-items: center;
  border-radius: 50%;
  background: rgba(111, 156, 128, 0.36);
  color: var(--card-white);
  font-size: 2rem;
  line-height: 1;
  transition:
    background 160ms var(--ease),
    box-shadow 160ms var(--ease),
    opacity 160ms var(--ease),
    transform 160ms var(--ease);
}

.sendButtonReady {
  background: var(--sage);
  box-shadow: var(--shadow-sage);
}

.sendButton:hover:not(:disabled) {
  background: var(--sage);
  transform: translateY(-1px);
}

.sendButtonReady:hover:not(:disabled),
.sendButtonReady:focus-visible {
  background: var(--sage-deep);
}

.sendButton:focus-visible {
  outline: 3px solid rgba(111, 156, 128, 0.28);
  outline-offset: 3px;
}

.sendButton:disabled,
.input:disabled {
  opacity: 0.58;
}

.sendButton:disabled {
  box-shadow: none;
  transform: none;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```bash
pnpm --filter @emoedu/student test -- Composer.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit task 2**

```bash
git add frontend/student/src/components/Composer.tsx frontend/student/src/components/Composer.module.css frontend/student/src/components/Composer.test.tsx
git commit -m "feat: mark student composer send readiness"
```

### Task 3: Final Verification

**Files:**
- No new files.

- [ ] **Step 1: Run the targeted student tests**

Run:

```bash
pnpm --filter @emoedu/student test -- App.waiting-state.test.tsx Composer.test.tsx
```

Expected: PASS.

- [ ] **Step 2: Run all student tests**

Run:

```bash
pnpm --filter @emoedu/student test
```

Expected: PASS.

- [ ] **Step 3: Run student typecheck**

Run:

```bash
pnpm --filter @emoedu/student typecheck
```

Expected: PASS.

- [ ] **Step 4: Run student build**

Run:

```bash
pnpm --filter @emoedu/student build
```

Expected: PASS.

- [ ] **Step 5: Commit verification-only updates if needed**

If verification requires no code changes, do not create a commit. If a fix was needed, commit only that fix:

```bash
git add frontend/student
git commit -m "fix: stabilize student chat waiting states"
```
