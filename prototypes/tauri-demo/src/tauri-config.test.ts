import { describe, expect, it } from "vitest";

import tauriConfig from "../src-tauri/tauri.conf.json";

/**
 * Guards the CSP decisions documented in the README: the packaged app must keep
 * a real policy (not `null`), and neither policy may fall back to
 * `'unsafe-eval'`. Both policies were additionally exercised in a browser —
 * see README → Notes and gotchas.
 */
describe("tauri.conf.json security", () => {
  it("keeps a content security policy for the packaged app", () => {
    const { csp } = tauriConfig.app.security;

    expect(csp).toBeTruthy();
    expect(csp).toContain("script-src 'self'");
    expect(csp).toContain("connect-src 'self' ipc:");
    expect(csp).not.toContain("unsafe-eval");
  });

  it("allows the dev server and HMR socket in the development policy only", () => {
    const { csp, devCsp } = tauriConfig.app.security;

    expect(devCsp).toContain("ws://localhost:1420");
    // Vite inlines the React Refresh preamble in dev.
    expect(devCsp).toContain("unsafe-inline");
    expect(devCsp).not.toContain("unsafe-eval");
    expect(csp).not.toContain("ws://");
  });
});
