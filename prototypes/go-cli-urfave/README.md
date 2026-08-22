# go-cli-urfave

Go CLI built with [urfave/cli](https://github.com/urfave/cli) **v3** — a hands-on
playground for the official docs at <https://cli.urfave.org/>. The project
started as a minimal experiment (originally under `research/experiments/`)
validating the framework while reading the [Lux](https://github.com/iawia002/lux)
video downloader source, and was later migrated from v2 to v3.

- Created: 2026-08-03 · Updated: 2026-08-22 · Status: `working`

## Quick start

```bash
just build              # compile into ./bin/greet
just run hello -n Ada   # or: go run . hello -n Ada
```

## Usage

```
greet                     # root action → "Hello, World!"
greet --name Ada          # global flag → "Hello, Ada!"
greet --name ""           # error: --name must not be empty (exit 2)
greet hello -n Ada        # subcommand + inherited global flag
greet bye                 # "Goodbye, World!"
greet b                   # alias for bye → "Goodbye, World!"
greet team add Bob --role lead   # nested subcommand + local flag
greet team remove Bob
greet hello extra         # error: hello takes no arguments (exit 2)
greet helo                # error: unknown command or unexpected argument "helo" (exit 2)
greet --help              # generated help (also: greet team --help)
```

The binary exits with code `2` on usage errors: an unknown command, a missing
positional argument, unexpected extra arguments, or an empty `--name`
(`cli.Exit("...", 2)`).

## About urfave/cli v3

[urfave/cli](https://cli.urfave.org/) is a **declarative**, simple, fast, and
fun package for building command line tools in Go. Feature highlights:

- commands and subcommands with alias and prefix-match support
- flexible and permissive help system (auto-generated `--help` text)
- dynamic shell completion for `bash`, `zsh`, `fish`, and `powershell`
- `man` and markdown documentation generation
- input flags for simple types, slices, time, duration, and more
- compound short flags (`-a -b -c` → `-abc`)
- value sources: flags can read from the command line, environment variables,
  plain-text files, or structured files via the separate `urfave/cli-altsrc` module

v3 is the recommended version for all new development
(`go get github.com/urfave/cli/v3@latest`); the v2 series receives security and
bug fixes only.

### v3 API at a glance

In v3 the app is a `cli.Command` (v2's `cli.App` was renamed), and every
handler takes a stdlib `context.Context` plus a `*cli.Command`:

```go
cmd := &cli.Command{
    Name:    "greet",
    Usage:   "a friendly CLI",
    Flags: []cli.Flag{
        &cli.StringFlag{Name: "name", Aliases: []string{"n"}, Value: "World"},
    },
    Action: func(ctx context.Context, cmd *cli.Command) error {
        fmt.Printf("Hello, %s!\n", cmd.String("name"))
        return nil
    },
    Commands: []*cli.Command{ /* subcommands, possibly nested */ },
}

if err := cmd.Run(context.Background(), os.Args); err != nil {
    fmt.Fprintln(os.Stderr, err)
    os.Exit(1)
}
```

(main.go uses plain stderr output here instead of `log.Fatal` to avoid a
timestamped duplicate of cli's own usage-error messages.)

Key differences from v2:

| v2                                  | v3                                             |
| ----------------------------------- | ---------------------------------------------- |
| `cli.App`                           | `cli.Command`                                  |
| `app.Run(os.Args)`                  | `cmd.Run(ctx, os.Args)`                        |
| `func(*cli.Context) error` handlers | `func(context.Context, *cli.Command) error`    |
| `Subcommands: []*cli.Command`       | `Commands: []*cli.Command`                     |
| `EnvVars` / `FilePath` on flags     | `Sources: cli.EnvVars(...)` / `cli.Files(...)` |
| `cli.Context` object                | merged into `cli.Command`                      |

See [main.go](./main.go) for a commented walkthrough of all of the above, and
the official docs for the full guide: [getting started](https://cli.urfave.org/v3/getting-started/),
[subcommands](https://cli.urfave.org/v3/examples/subcommands/basics/), and the
[v2 → v3 migration guide](https://cli.urfave.org/migrate-v2-to-v3/).

## Debugging with VS Code

A Go launch configuration ships with the prototype in
`.vscode/launch.json`, so the debugger works right after cloning.

1. Install the
   [Go extension](https://marketplace.visualstudio.com/items?itemName=golang.go)
   (`golang.go`) — the first debug session auto-installs the Delve debugger.
1. Open the prototype folder in VS Code (`code prototypes/go-cli-urfave`) —
   the Go module is detected from its `go.mod`.
1. Open `main.go`, set a breakpoint (e.g. inside the root `Action` or a
   subcommand handler), then open **Run and Debug** (`Ctrl/Cmd+Shift+D`),
   pick **Debug go-cli-urfave (Go)** and press `F5`. `greet` runs with no
   arguments, so the root action executes.

To debug a specific subcommand, add the arguments to the `"args"` array of
`.vscode/launch.json` and press `F5` again:

```json
"args": ["team", "add", "Bob", "--role", "lead"]
```

`cwd` is already set to the prototype directory, so relative paths behave
exactly like `just run`. Debugger cheatsheet: `F5` start/continue, `F10` step
over, `F11` step into, `Shift+F5` stop — see the
[VS Code debugging docs](https://code.visualstudio.com/docs/editor/debugging).

> Note: when opening the whole repo root instead of the prototype folder,
> the repo-root `.vscode/launch.json` is local-only (gitignored) — add the
> same entry there to get the dropdown item, mirroring the other prototype
> debug configs.

## Recipes

Run `just` (no args) to list all recipes:

| Recipe       | Description                                                   |
| ------------ | ------------------------------------------------------------- |
| `just build` | compile the CLI into `./bin/greet`                            |
| `just run`   | build and run, forwarding args (e.g. `just run hello -n Ada`) |
| `just fmt`   | `gofmt` + `go vet`                                            |
| `just vet`   | run `go vet ./...`                                            |
| `just test`  | run `go test ./...` (no tests yet)                            |
| `just clean` | remove `bin/`                                                 |
