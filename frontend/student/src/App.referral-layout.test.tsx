import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchStudentChatStream } from "@emoedu/shared";
import App from "./App";

vi.mock("@emoedu/shared", () => ({
  clearAnonymousMemory: vi.fn().mockResolvedValue(undefined),
  fetchStudentChatStream: vi.fn(),
}));

const fetchStudentChatStreamMock = vi.mocked(fetchStudentChatStream);

describe("student referral layout", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    fetchStudentChatStreamMock.mockResolvedValue({
      session_id: "session-a",
      anonymous_user_id: "anon-a",
      reply_text: "referral",
      risk_level: "red",
    });
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("marks the chat scroll area when referral resources replace the composer", async () => {
    render(<App />);

    const input = screen.getByRole("textbox", { name: "输入消息" });
    fireEvent.change(input, { target: { value: "crisis" } });
    fireEvent.keyDown(input, { key: "Enter" });

    await waitFor(() => {
      expect(screen.getByTestId("student-chat-scroll").dataset.referralLocked).toBe(
        "true",
      );
    });
    expect(screen.getByText("12356")).toBeTruthy();
    expect(screen.getByText("120")).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: "输入消息" })).toBeNull();
  });

  it("keeps the composer available for yellow support and lets the card collapse", async () => {
    fetchStudentChatStreamMock.mockResolvedValueOnce({
      session_id: "session-a",
      anonymous_user_id: "anon-a",
      reply_text: "yellow reply",
      risk_level: "yellow",
    });

    render(<App />);

    const input = screen.getByRole("textbox", { name: "输入消息" });
    fireEvent.change(input, { target: { value: "我很难过" } });
    fireEvent.keyDown(input, { key: "Enter" });

    expect(await screen.findByText("yellow reply")).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "输入消息" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "我注意到你可能需要更多支持" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "关闭支持提示" }));

    expect(
      screen.queryByRole("heading", { name: "我注意到你可能需要更多支持" }),
    ).toBeNull();
    expect(screen.getByText("需要支持时，可以查看资源")).toBeTruthy();
    expect(screen.getByRole("textbox", { name: "输入消息" })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "查看资源" }));

    expect(screen.getByRole("heading", { name: "我注意到你可能需要更多支持" })).toBeTruthy();
  });

  it("hides the collapsed yellow support entry after a green response", async () => {
    fetchStudentChatStreamMock
      .mockResolvedValueOnce({
        session_id: "session-a",
        anonymous_user_id: "anon-a",
        reply_text: "yellow reply",
        risk_level: "yellow",
      })
      .mockResolvedValueOnce({
        session_id: "session-a",
        anonymous_user_id: "anon-a",
        reply_text: "green reply",
        risk_level: "green",
      });

    render(<App />);

    const input = screen.getByRole("textbox", { name: "输入消息" });
    fireEvent.change(input, { target: { value: "我很难过" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(await screen.findByText("yellow reply")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "关闭支持提示" }));
    expect(screen.getByText("需要支持时，可以查看资源")).toBeTruthy();

    const nextInput = screen.getByRole("textbox", { name: "输入消息" });
    fireEvent.change(nextInput, { target: { value: "现在好一点了" } });
    fireEvent.keyDown(nextInput, { key: "Enter" });

    expect(await screen.findByText("green reply")).toBeTruthy();
    expect(screen.queryByText("需要支持时，可以查看资源")).toBeNull();
  });
});
