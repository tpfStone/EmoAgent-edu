// @vitest-environment node

import { describe, expect, it } from "vitest";
import type { UserConfig } from "vite";
import config from "./vite.config";

describe("student dev proxy", () => {
  it("proxies both chat and api calls in live mode", () => {
    const proxy = (config as UserConfig).server?.proxy as Record<string, unknown>;

    expect(proxy).toHaveProperty("/chat");
    expect(proxy).toHaveProperty("/api");
  });
});
