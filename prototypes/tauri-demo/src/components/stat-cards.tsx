import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Meter } from "@/components/meter";
import { formatBytes, formatPercent, formatUptime } from "@/lib/format";
import type { Snapshot } from "@/lib/ipc";

interface StatCardsProps {
  snapshot: Snapshot | null;
}

interface StatCardProps {
  title: string;
  value: string;
  detail: string;
  progress?: number;
  testId: string;
}

function StatCard({ title, value, detail, progress, testId }: StatCardProps) {
  return (
    <Card data-testid={testId}>
      <CardHeader>
        <CardDescription>{title}</CardDescription>
        <CardTitle className="text-2xl tabular-nums" data-testid={`${testId}-value`}>
          {value}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {typeof progress === "number" ? (
          <Meter value={progress} label={`${title} usage`} testId={`${testId}-bar`} />
        ) : null}
        <p className="text-xs text-muted-foreground">{detail}</p>
      </CardContent>
    </Card>
  );
}

/** CPU / memory / disk / uptime summary cards. */
export function StatCards({ snapshot }: StatCardsProps) {
  if (!snapshot) {
    return (
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" data-testid="stat-cards-loading">
        {Array.from({ length: 4 }, (_, index) => (
          <Card key={index}>
            <CardHeader>
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-7 w-20" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-1.5 w-full" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  const memoryPercent =
    snapshot.memoryTotal > 0 ? (snapshot.memoryUsed / snapshot.memoryTotal) * 100 : 0;
  const diskTotal = snapshot.disks.reduce((sum, disk) => sum + disk.total, 0);
  const diskUsed = snapshot.disks.reduce((sum, disk) => sum + disk.used, 0);
  const diskPercent = diskTotal > 0 ? (diskUsed / diskTotal) * 100 : 0;

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard
        testId="stat-cpu"
        title="CPU"
        value={formatPercent(snapshot.cpuUsage)}
        detail={`${snapshot.cores.length} cores`}
        progress={snapshot.cpuUsage}
      />
      <StatCard
        testId="stat-memory"
        title="Memory"
        value={formatPercent(memoryPercent)}
        detail={`${formatBytes(snapshot.memoryUsed)} / ${formatBytes(snapshot.memoryTotal)}`}
        progress={memoryPercent}
      />
      <StatCard
        testId="stat-disk"
        title="Disk"
        value={formatPercent(diskPercent)}
        detail={`${formatBytes(diskUsed)} / ${formatBytes(diskTotal)}`}
        progress={diskPercent}
      />
      <StatCard
        testId="stat-uptime"
        title="Uptime"
        value={formatUptime(snapshot.uptimeSecs)}
        detail={`Swap ${formatBytes(snapshot.swapUsed)} / ${formatBytes(snapshot.swapTotal)}`}
      />
    </div>
  );
}
