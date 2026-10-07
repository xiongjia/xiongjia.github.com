import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Meter } from "@/components/meter";
import { formatPercent } from "@/lib/format";
import type { CpuCore } from "@/lib/ipc";

interface CoresGridProps {
  cores: CpuCore[];
}

/** Per-core CPU usage, straight from `sysinfo` via the IPC layer. */
export function CoresGrid({ cores }: CoresGridProps) {
  return (
    <Card data-testid="cores-grid">
      <CardHeader>
        <CardTitle>Per-core load</CardTitle>
        <CardDescription>{cores.length} logical cores</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
          {cores.map((core) => (
            <div key={core.core} className="space-y-1">
              <div className="flex items-baseline justify-between text-xs">
                <span className="text-muted-foreground">core {core.core}</span>
                <span className="tabular-nums">{formatPercent(core.usage)}</span>
              </div>
              <Meter
                value={core.usage}
                label={`core ${core.core} usage`}
                barClassName="bg-[var(--chart-2)]"
              />
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
