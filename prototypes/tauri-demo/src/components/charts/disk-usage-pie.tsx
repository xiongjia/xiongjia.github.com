import { Cell, Pie, PieChart } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import { formatBytes, formatPercent } from "@/lib/format";
import type { DiskUsage } from "@/lib/ipc";

const CHART_COLORS = ["var(--chart-1)", "var(--chart-2)", "var(--chart-3)", "var(--chart-4)", "var(--chart-5)"];

interface DiskUsagePieProps {
  disks: DiskUsage[];
}

/** Used space per mount point (donut) plus a per-disk detail table. */
export function DiskUsagePie({ disks }: DiskUsagePieProps) {
  // Two volumes can share a mount point (APFS containers), so series are keyed
  // by position instead of by mount point. Unnamed volumes that also lack a
  // mount point still need *something* to render.
  const data = disks.map((disk, index) => ({
    series: `disk-${index}`,
    mountPoint: disk.mountPoint,
    label: disk.name || disk.mountPoint || `volume ${index + 1}`,
    used: disk.used,
    total: disk.total,
    available: disk.available,
    fill: CHART_COLORS[index % CHART_COLORS.length],
  }));

  const chartConfig = Object.fromEntries(
    data.map((entry) => [entry.series, { label: entry.label, color: entry.fill }]),
  ) satisfies ChartConfig;

  return (
    <Card data-testid="chart-disk-usage">
      <CardHeader>
        <CardTitle>Disk usage</CardTitle>
        <CardDescription>Used space per mount point (APFS volumes can share one container)</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <ChartContainer config={chartConfig} className="mx-auto h-[220px] w-full max-w-[320px]">
          <PieChart>
            <ChartTooltip
              cursor={false}
              content={<ChartTooltipContent hideLabel nameKey="label" />}
            />
            <Pie
              data={data}
              dataKey="used"
              nameKey="mountPoint"
              innerRadius={58}
              outerRadius={92}
              strokeWidth={2}
              isAnimationActive={false}
            >
              {data.map((entry) => (
                <Cell key={entry.series} fill={entry.fill} />
              ))}
            </Pie>
          </PieChart>
        </ChartContainer>

        <ul className="space-y-2" data-testid="disk-list">
          {data.map((entry) => {
            const percent = entry.total > 0 ? (entry.used / entry.total) * 100 : 0;
            return (
              <li key={entry.series} className="flex items-center justify-between gap-3 text-sm">
                <span className="flex min-w-0 items-center gap-2">
                  <span
                    aria-hidden
                    className="size-2.5 shrink-0 rounded-full"
                    style={{ backgroundColor: entry.fill }}
                  />
                  <span className="truncate font-medium">{entry.label}</span>
                  {entry.mountPoint && entry.label !== entry.mountPoint ? (
                    <span className="truncate text-xs text-muted-foreground">{entry.mountPoint}</span>
                  ) : null}
                </span>
                <span className="shrink-0 text-muted-foreground tabular-nums">
                  {formatBytes(entry.used)} / {formatBytes(entry.total)} ({formatPercent(percent)}) ·{" "}
                  {formatBytes(entry.available)} free
                </span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
