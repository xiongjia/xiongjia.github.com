import { describe, expect, it } from "vitest";
import { DEMO_PAGE_HTML, DEMO_SELECTORS } from "./demo.page";

describe("demo page", () => {
  it("contains every selector the visitor relies on", () => {
    for (const selector of Object.values(DEMO_SELECTORS)) {
      expect(DEMO_PAGE_HTML).toContain(`id="${selector.slice(1)}"`);
    }
  });

  it("starts with the delayed element hidden and reveals it by script", () => {
    expect(DEMO_PAGE_HTML).toContain("#delayed { visibility: hidden;");
    expect(DEMO_PAGE_HTML).toContain("setTimeout");
  });

  it("does not load anything from the network", () => {
    expect(DEMO_PAGE_HTML).not.toMatch(/https?:\/\//);
  });
});
