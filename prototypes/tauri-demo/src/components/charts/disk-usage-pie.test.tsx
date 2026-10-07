import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DiskUsagePie } from "@/components/charts/disk-usage-pie";
import { snapshotFixture } from "@/test/fixtures";
import { chartSurfaceCount, pieSectorCount } from "@/test/recharts";

describe("DiskUsagePie", () => {
  it("renders one sector per mount point plus the detail list", () => {
    const { container } = render(<DiskUsagePie disks={snapshotFixture.disks} />);

    expect(chartSurfaceCount(container)).toBe(1);
    expect(pieSectorCount(container)).toBe(snapshotFixture.disks.length);
    expect(screen.getByTestId("disk-list").querySelectorAll("li").length).toBe(
      snapshotFixture.disks.length,
    );
  });

  it("shows the volume name, mount point and free space per disk", () => {
    render(<DiskUsagePie disks={snapshotFixture.disks} />);

    expect(screen.getByText("Macintosh HD")).toBeTruthy();
    expect(screen.getByText("Data")).toBeTruthy();
    expect(screen.getAllByText("60.0 GiB / 100.0 GiB (60%) · 40.0 GiB free").length).toBe(
      snapshotFixture.disks.length,
    );
  });

  it("falls back to the mount point when a volume has no name", () => {
    render(
      <DiskUsagePie
        disks={[{ name: "", mountPoint: "/media/usb", total: 1024, available: 512, used: 512 }]}
      />,
    );

    expect(screen.getByText("/media/usb")).toBeTruthy();
  });

  it("labels a volume that has neither a name nor a mount point", () => {
    render(
      <DiskUsagePie
        disks={[{ name: "", mountPoint: "", total: 2048, available: 1024, used: 1024 }]}
      />,
    );

    expect(screen.getByText("volume 1")).toBeTruthy();
  });

  it("keeps two volumes that share a mount point apart", () => {
    const { container } = render(
      <DiskUsagePie
        disks={[
          { name: "A", mountPoint: "/", total: 100, available: 40, used: 60 },
          { name: "B", mountPoint: "/", total: 200, available: 40, used: 160 },
        ]}
      />,
    );

    expect(pieSectorCount(container)).toBe(2);
    expect(screen.getByText("A")).toBeTruthy();
    expect(screen.getByText("B")).toBeTruthy();
  });
});
