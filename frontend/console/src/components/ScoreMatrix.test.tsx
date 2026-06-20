import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ScoreMatrix } from "./ScoreMatrix";

describe("ScoreMatrix", () => {
  afterEach(() => {
    cleanup();
  });

  it("uses the caller-provided empty reason when F4 is still pending", () => {
    render(
      <ScoreMatrix
        emptyReason="F4 guidance is still running."
        preferencePair={null}
        scores={[]}
      />,
    );

    expect(screen.getByText("F4 guidance is still running.")).toBeTruthy();
    expect(screen.queryByText(/安全门拦截/)).toBeNull();
  });
});
