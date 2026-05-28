import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";

describe("research console module transitions", () => {
  afterEach(() => {
    cleanup();
  });

  it("wraps tab switches in a transition container with observable state", () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /批量证据/ }));

    const transition = screen.getByTestId("console-main-transition");
    expect(transition.getAttribute("data-transition-key")).toBe("batch");
    expect(transition.getAttribute("data-transition-state")).toMatch(
      /^(entering|entered|exiting)$/,
    );
  });
});
