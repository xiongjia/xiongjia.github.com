import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CoresGrid } from "@/components/cores-grid";
import { StatCards } from "@/components/stat-cards";
import { ThemeToggle } from "@/components/theme-toggle";
import { CpuMemoryLine } from "@/components/charts/cpu-memory-line";
import { DiskUsagePie } from "@/components/charts/disk-usage-pie";
import { TopProcessesBar } from "@/components/charts/top-processes-bar";
import { useSystemStats } from "@/hooks/use-system-stats";
import { isDesktopApp } from "@/lib/ipc";

function App() {
  const { snapshot, history, error } = useSystemStats();

  return (
    <main className="mx-auto flex min-h-screen w-full max-w-6xl flex-col gap-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Tauri Demo</h1>
          <p className="text-sm text-muted-foreground">
            Rust collects the metrics, React renders them with shadcn charts.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {snapshot ? (
            <span className="text-xs text-muted-foreground tabular-nums" data-testid="last-updated">
              updated {new Date(snapshot.timestampMs).toLocaleTimeString()}
            </span>
          ) : null}
          <Badge variant="secondary" data-testid="runtime-badge">
            {isDesktopApp() ? "Tauri / Rust" : "Browser mock"}
          </Badge>
          <ThemeToggle />
        </div>
      </header>

      {error ? (
        <div
          role="alert"
          data-testid="stats-error"
          className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
        >
          Failed to read system metrics: {error}
        </div>
      ) : null}

      <StatCards snapshot={snapshot} />

      <Tabs defaultValue="overview" data-testid="stats-tabs">
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="processes">Processes</TabsTrigger>
          <TabsTrigger value="disks">Disks</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-4 grid gap-4 lg:grid-cols-2">
          <CpuMemoryLine history={history} capacity={snapshot?.historyCapacity} />
          <CoresGrid cores={snapshot?.cores ?? []} />
        </TabsContent>

        <TabsContent value="processes" className="mt-4">
          <TopProcessesBar processes={snapshot?.topProcesses ?? []} />
        </TabsContent>

        <TabsContent value="disks" className="mt-4">
          <DiskUsagePie disks={snapshot?.disks ?? []} />
        </TabsContent>
      </Tabs>
    </main>
  );
}

export default App;
