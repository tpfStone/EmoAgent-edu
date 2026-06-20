import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Composer } from "./Composer";

describe("Composer", () => {
  afterEach(() => {
    cleanup();
  });

  it("marks the send button ready only when text can be sent", () => {
    render(<Composer onSend={vi.fn()} />);

    const input = screen.getByRole("textbox", { name: "输入消息" });
    const sendButton = screen.getByRole("button", { name: "发送" });

    expect((sendButton as HTMLButtonElement).disabled).toBe(true);
    expect(sendButton.getAttribute("data-send-ready")).toBe("false");

    fireEvent.change(input, { target: { value: "hello" } });

    expect((sendButton as HTMLButtonElement).disabled).toBe(false);
    expect(sendButton.getAttribute("data-send-ready")).toBe("true");
  });

  it("does not mark the send button ready while loading", () => {
    render(<Composer loading={true} onSend={vi.fn()} />);

    const input = screen.getByRole("textbox", { name: "输入消息" });
    const sendButton = screen.getByRole("button", { name: "正在回应" });

    fireEvent.change(input, { target: { value: "hello" } });

    expect((sendButton as HTMLButtonElement).disabled).toBe(true);
    expect(sendButton.getAttribute("data-send-ready")).toBe("false");
  });
});
