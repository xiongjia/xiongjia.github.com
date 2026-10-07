import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CoresGrid } from "@/components/cores-grid";
import { snapshotFixture } from "@/test/fixtures";

describe("CoresGrid", () => {
  it("renders one row per logical core", () => {
    render(<CoresGrid cores={snapshotFixture.cores} />);

    const rows = screen.getByTestId("cores-grid").querySelectorAll(".tabular-nums");
    expect(rows.length).toBe(snapshotFixture.cores.length);
    expect(screen.getByText("core 0")).toBeTruthy();
    expect(screen.getByText("88%")).toBeTruthy();
  });

  it("labels every core meter for assistive technology", () => {
    render(<CoresGrid cores={snapshotFixture.cores} />);

    const meters = screen.getAllByRole("progressbar");
    expect(meters).toHaveLength(snapshotFixture.cores.length);
    expect(screen.getByRole("progressbar", { name: "core 1 usage" }).getAttribute("aria-valuenow")).toBe(
      "88",
    );
  });

  it("renders an empty grid without crashing", () => {
    render(<CoresGrid cores={[]} />);

    expect(screen.getByTestId("cores-grid").textContent).toContain("0 logical cores");
    expect(screen.queryAllByRole("progressbar")).toHaveLength(0);
  });
});
