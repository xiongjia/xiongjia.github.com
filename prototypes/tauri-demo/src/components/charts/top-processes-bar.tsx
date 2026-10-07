import { Bar, BarChart, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ChartContainer, ChartTooltip, ChartTooltipContent, type ChartConfig } from "@/components/ui/chart";
import type { ProcessUsage } from "@/lib/ipc";

const chartConfig = {
  memoryMiB: { label: "Memory", color: "var(--chart-3)" },
} satisfies ChartConfig;

const MAX_LABEL_LENGTH = 18;

interface TopProcessesBarProps {
  processes: ProcessUsage[];
}

/**
 * Truncates by code point (so emoji/CJK names are never cut mid-character).
 */
function truncate(name: string): string {
  const characters = Array.from(name);
  return characters.length > MAX_LABEL_LENGTH
    ? `${characters.slice(0, MAX_LABEL_LENGTH - 1).join("")}…`
    : name;
}

/** Top processes by resident memory (horizontal bars). */
export function TopProcessesBar({ processes }: TopProcessesBarProps) {
  // Several helpers of the same app share a prefix ("Google Chrome Helper"),
  // and Recharts needs distinct category values, so colliding labels get a pid.
  const truncated = processes.map((process) => truncate(process.name));
  const occurrences = new Map<string, number>();
  for (const label of truncated) {
    occurrences.set(label, (occurrences.get(label) ?? 0) + 1);
  }

  const data = processes.map((process, index) => {
    const label = truncated[index];
    return {
      name: (occurrences.get(label) ?? 0) > 1 ? `${label} #${process.pid}` : label,
      memoryMiB: Number((process.memory / 1024 ** 2).toFixed(1)),
    };
  });

  return (
    <Card data-testid="chart-top-processes">
      <CardHeader>
        <CardTitle>Top processes by memory</CardTitle>
        <CardDescription>
          {processes.length > 0
            ? `${processes.length} processes, sorted by resident memory`
            : "Waiting for data"}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[300px] w-full">
          <BarChart data={data} layout="vertical" margin={{ left: 8, right: 24 }}>
            <XAxis type="number" hide />
            <YAxis
              type="category"
              dataKey="name"
              width={132}
              tickLine={false}
              axisLine={false}
            />
            <ChartTooltip
              cursor={false}
              content={<ChartTooltipContent formatter={(value) => `${String(value)} MiB`} />}
            />
            <Bar
              dataKey="memoryMiB"
              name="Memory"
              fill="var(--color-memoryMiB)"
              radius={4}
              isAnimationActive={false}
            />
          </BarChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
