import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import { formatClock } from "@/lib/format";
import type { HistoryPoint } from "@/lib/ipc";

const chartConfig = {
  cpu: { label: "CPU", color: "var(--chart-1)" },
  memory: { label: "Memory", color: "var(--chart-2)" },
} satisfies ChartConfig;

interface CpuMemoryLineProps {
  history: HistoryPoint[];
  /** Ring-buffer size reported by the Rust side, for the card description. */
  capacity?: number;
}

/** CPU + memory usage over time, fed by the Rust history ring buffer. */
export function CpuMemoryLine({ history, capacity }: CpuMemoryLineProps) {
  const data = history.map((point) => ({
    time: formatClock(point.timestampMs),
    cpu: Number(point.cpu.toFixed(1)),
    memory: Number(point.memory.toFixed(1)),
  }));

  const description =
    capacity === undefined
      ? `Last ${history.length} samples, one every 2 seconds`
      : `Last ${history.length} of ${capacity} samples, one every 2 seconds`;

  return (
    <Card data-testid="chart-cpu-memory">
      <CardHeader>
        <CardTitle>CPU &amp; memory</CardTitle>
        <CardDescription>{description}</CardDescription>
      </CardHeader>
      <CardContent>
        <ChartContainer config={chartConfig} className="h-[260px] w-full">
          <LineChart data={data} margin={{ left: 4, right: 12, top: 8 }}>
            <CartesianGrid vertical={false} />
            <XAxis dataKey="time" tickLine={false} axisLine={false} tickMargin={8} />
            <YAxis
              domain={[0, 100]}
              width={36}
              tickLine={false}
              axisLine={false}
              tickFormatter={(value: number) => `${value}%`}
            />
            <ChartTooltip content={<ChartTooltipContent />} />
            <ChartLegend content={<ChartLegendContent />} />
            <Line
              dataKey="cpu"
              type="monotone"
              stroke="var(--color-cpu)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              dataKey="memory"
              type="monotone"
              stroke="var(--color-memory)"
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ChartContainer>
      </CardContent>
    </Card>
  );
}
