import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchStudentChat } from "@emoedu/shared";
import { useStudentChat } from "./useStudentChat";

vi.mock("@emoedu/shared", () => ({
  fetchStudentChat: vi.fn(),
}));

const fetchStudentChatMock = vi.mocked(fetchStudentChat);

function Harness() {
  const { referralLocked, riskLevel, send } = useStudentChat("session-a");

  return (
    <div>
      <p>risk:{riskLevel}</p>
      <p>locked:{String(referralLocked)}</p>
      <button type="button" onClick={() => void send("message")}>
        send
      </button>
    </div>
  );
}

describe("useStudentChat conservative fallback", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("does not downgrade the last known non-green risk when chat fetch fails", async () => {
    fetchStudentChatMock
      .mockResolvedValueOnce({
        session_id: "session-a",
        reply_text: "我先陪你把这件事稳住。",
        risk_level: "yellow",
      })
      .mockRejectedValueOnce(new Error("offline"));

    render(<Harness />);

    fireEvent.click(screen.getByRole("button", { name: "send" }));

    expect(await screen.findByText("risk:yellow")).toBeTruthy();
    expect(screen.getByText("locked:true")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "send" }));

    await waitFor(() => expect(fetchStudentChatMock).toHaveBeenCalledTimes(2));
    expect(screen.getByText("risk:yellow")).toBeTruthy();
    expect(screen.getByText("locked:true")).toBeTruthy();
  });
});
