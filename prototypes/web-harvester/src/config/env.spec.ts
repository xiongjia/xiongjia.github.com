import { describe, expect, it } from "vitest";
import { validateEnv } from "./env";

describe("validateEnv", () => {
  it("applies defaults when nothing is set", () => {
    const env = validateEnv({});
    expect(env.HARVEST_HOST).toBe("127.0.0.1");
    expect(env.HARVEST_PORT).toBe(8765);
    // Unset on purpose: every profile keeps its own engine, and a new profile is
    // created as camoufox. Setting it turns the variable into a global override.
    expect(env.HARVEST_BROWSER).toBeUndefined();
    expect(env.HARVEST_SLOWMO).toBe(0);
    // addons.mozilla.org answers 451 here, so the default addon is skipped
    expect(env.HARVEST_EXCLUDE_ADDONS).toEqual(["UBO"]);
    expect(env.HARVEST_HEADLESS).toBe(true);
  });

  it("coerces numbers and booleans from strings", () => {
    const env = validateEnv({
      HARVEST_PORT: "9000",
      HARVEST_HEADLESS: "false",
      HARVEST_SLOWMO: "250",
    });
    expect(env.HARVEST_PORT).toBe(9000);
    expect(env.HARVEST_HEADLESS).toBe(false);
    expect(env.HARVEST_SLOWMO).toBe(250);
  });

  it("keeps the virtual headless mode used for Xvfb runs", () => {
    expect(validateEnv({ HARVEST_HEADLESS: "virtual" }).HARVEST_HEADLESS).toBe(
      "virtual",
    );
  });

  it("parses the addon exclusion list and allows clearing it", () => {
    expect(
      validateEnv({ HARVEST_EXCLUDE_ADDONS: "ubo" }).HARVEST_EXCLUDE_ADDONS,
    ).toEqual(["UBO"]);
    expect(
      validateEnv({ HARVEST_EXCLUDE_ADDONS: "" }).HARVEST_EXCLUDE_ADDONS,
    ).toEqual([]);
    expect(
      validateEnv({ HARVEST_EXCLUDE_ADDONS: "uBO, ublock" })
        .HARVEST_EXCLUDE_ADDONS,
    ).toEqual(["UBO", "UBLOCK"]);
  });

  it("accepts an explicit fingerprint OS and rejects unknown ones", () => {
    expect(validateEnv({ HARVEST_OS: "windows" }).HARVEST_OS).toBe("windows");
    expect(validateEnv({}).HARVEST_OS).toBeUndefined();
    expect(() => validateEnv({ HARVEST_OS: "beos" })).toThrow(
      /Invalid environment/,
    );
  });

  it("rejects an unknown backend", () => {
    expect(() => validateEnv({ HARVEST_BROWSER: "chrome" })).toThrow(
      /Invalid environment/,
    );
  });

  it("accepts every engine, including the stealth Chromium one", () => {
    expect(
      validateEnv({ HARVEST_BROWSER: "cloakbrowser" }).HARVEST_BROWSER,
    ).toBe("cloakbrowser");
    expect(validateEnv({ HARVEST_BROWSER: "patchright" }).HARVEST_BROWSER).toBe(
      "patchright",
    );
    expect(validateEnv({ HARVEST_BROWSER: "camoufox" }).HARVEST_BROWSER).toBe(
      "camoufox",
    );
  });
});
