import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import App from "./App";

describe("student module transitions", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("wraps main view switches in a transition container with observable state", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: "整理记录" }));

    const transition = screen.getByTestId("student-main-transition");
    expect(transition.getAttribute("data-transition-key")).toBe("records");
    expect(transition.getAttribute("data-transition-state")).toMatch(
      /^(entering|entered|exiting)$/,
    );
  });
});
