import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";

const acceptanceDocPath =
  "docs/acceptance/orchestrator-mvp/2026-05-21/2026-05-21-orchestrator-mvp-test-summary.md";

describe("research console evidence presentation", () => {
  afterEach(() => {
    cleanup();
  });

  it("shows a read-only student-visible reply preview in the single turn trace", () => {
    render(<App />);

    expect(screen.getByText("学生实际看到的回复")).toBeTruthy();
    expect(screen.getByText("只读预览，不连接学生端状态")).toBeTruthy();
  });

  it("shows the documented acceptance source path for batch evidence", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /批量证据/ }));

    expect(screen.getByText(`文档：${acceptanceDocPath}`)).toBeTruthy();
  });
});
