import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "./App";

const memoryNotice =
  "我现在只在这台设备上保留会话标题和消息，用来帮你回到刚才的话题。跨会话情绪画像还没有接入后端。";
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

  it("uses the emotion trajectory view as the only destructive memory action", () => {
    render(<App />);

    expect(screen.queryByRole("button", { name: "清空本地记忆" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "我的情绪轨迹" }));

    expect(screen.getByText(memoryNotice)).toBeTruthy();
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
