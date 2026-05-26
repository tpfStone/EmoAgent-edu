import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "./App";

const localHistoryNotice =
  '这里是你在这台设备上聊过的话题，方便你回到刚才的对话。我不会分析或记住"你是什么样的人"，也不会把这些发到别处。';
const breathingCopy = "吸气四秒，呼气四秒。";

describe("student screenshot-style information architecture", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("opens on a quiet chat surface without breathing guidance or a presence dot", () => {
    render(<App />);

    expect(screen.getByText("你可以慢慢说，我会认真听")).toBeTruthy();
    expect(
      screen.getByText("嗨，我在这儿。今天有什么想说的，随便聊聊就好，不用着急。"),
    ).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "嗯，我在。" })).toBeNull();
    expect(screen.queryByText(breathingCopy)).toBeNull();
    expect(screen.queryByLabelText("呼吸练习")).toBeNull();
    expect(screen.getByRole("textbox", { name: "输入消息" })).toBeTruthy();
  });

  it("uses local conversation history as the only destructive memory action", () => {
    render(<App />);

    expect(screen.queryByRole("button", { name: "清空本地记忆" })).toBeNull();
    expect(screen.queryByRole("button", { name: "我的情绪轨迹" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "我聊过的" }));

    expect(screen.getByText(localHistoryNotice)).toBeTruthy();
    expect(screen.getByRole("button", { name: "让我忘记" })).toBeTruthy();
    expect(screen.queryByRole("textbox", { name: "输入消息" })).toBeNull();
  });

  it("opens breathing as a separate main view instead of layering it over chat", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "静一静 · 呼吸" }));

    expect(screen.getAllByText(breathingCopy)).toHaveLength(1);
    expect(
      screen.queryByText("嗨，我在这儿。今天有什么想说的，随便聊聊就好，不用着急。"),
    ).toBeNull();
    expect(screen.queryByRole("textbox", { name: "输入消息" })).toBeNull();
  });
});
