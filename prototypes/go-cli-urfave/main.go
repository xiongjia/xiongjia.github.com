// Command-line interface built on urfave/cli v3.
//
// This file is a hands-on playground for the urfave/cli v3 API
// (https://cli.urfave.org/). It demonstrates the core building blocks:
//
//  1. Root command  — a `cli.Command` is the app itself (in v2 it was
//     `cli.App`; v3 renamed it to `cli.Command`).
//  2. Flags         — `Flags` are declared as concrete types
//     (`*cli.StringFlag`), with aliases (`-n`), defaults, and global scope
//     (inherited by every subcommand).
//  3. Subcommands   — `Commands: []*cli.Command` gives the CLI a git-like
//     structure: `greet <subcommand> [flags]`.
//  4. Nested commands — a subcommand may itself have `Commands`, enabling
//     two-level trees such as `greet team add <name>`.
//  5. Action        — every command runs an `Action` of the form
//     `func(context.Context, *cli.Command) error`; the first argument is a
//     stdlib `context.Context` (useful for timeouts/cancellation), the
//     second carries parsed flags, args, and other state.
//
// Run it with:  just run            (or: go run .)
package main

import (
	"context"
	"fmt"
	"os"

	"github.com/urfave/cli/v3"
)

func main() {
	// A `cli.Command` is both the app and any (sub)command — the root one
	// below is our whole program. `Run` parses os.Args, dispatches to the
	// matching subcommand (or the root Action), and generates --help text.
	cmd := &cli.Command{
		Name:    "greet",
		Version: "v0.1.0",
		Usage:   "a friendly CLI demonstrating the urfave/cli v3 API",

		// Flags declared on the root command are GLOBAL: every subcommand
		// inherits them, so `greet hello --name Ada` works too.
		Flags: []cli.Flag{
			&cli.StringFlag{
				Name:    "name",
				Aliases: []string{"n"}, // short form: -n
				Usage:   "name to greet",
				Value:   "World", // default when the flag is omitted
			},
		},

		// Root Action: runs when `greet` is invoked without a subcommand
		// (e.g. `greet` or `greet --name Ada`). Any positional argument that
		// does not match a subcommand lands here, so reject it instead of
		// silently running the root action.
		Action: func(ctx context.Context, cmd *cli.Command) error {
			if cmd.Args().Len() > 0 {
				return cli.Exit(fmt.Sprintf("unknown command or unexpected argument %q", cmd.Args().First()), 2)
			}
			return sayHello(cmd.String("name"))
		},

		// Subcommands make the CLI look like git: `greet <sub> [flags]`.
		Commands: []*cli.Command{
			{
				// Note: no "h" alias here — it would collide with the builtin
				// `help` command, which cli auto-registers as `help, h`.
				Name:  "hello",
				Usage: "say hello to someone",
				Action: func(ctx context.Context, cmd *cli.Command) error {
					// cmd.String reads a flag value; because "name" is a
					// global flag, it is visible here as well.
					if err := requireNoArgs(cmd); err != nil {
						return err
					}
					return sayHello(cmd.String("name"))
				},
			},
			{
				// Aliases let users type a shorter form: `greet b`.
				Name:    "bye",
				Aliases: []string{"b"},
				Usage:   "say goodbye to someone",
				Action: func(ctx context.Context, cmd *cli.Command) error {
					if err := requireNoArgs(cmd); err != nil {
						return err
					}
					return sayBye(cmd.String("name"))
				},
			},
			{
				// A subcommand with its own Commands = nested commands.
				// Run as:  greet team add Ada   /   greet team remove Ada
				Name:  "team",
				Usage: "manage a team roster (nested-command example)",
				Commands: []*cli.Command{
					{
						Name:      "add",
						Usage:     "add a member to the team",
						ArgsUsage: "<member-name>",
						// Flags declared here are LOCAL to this subcommand.
						Flags: []cli.Flag{
							&cli.StringFlag{
								Name:  "role",
								Usage: "role of the new member",
								Value: "member",
							},
						},
						Action: func(ctx context.Context, cmd *cli.Command) error {
							member, err := requireMember(cmd)
							if err != nil {
								return err
							}
							fmt.Printf("Added %s to the team as %s\n", member, cmd.String("role"))
							return nil
						},
					},
					{
						Name:      "remove",
						Usage:     "remove a member from the team",
						ArgsUsage: "<member-name>",
						Action: func(ctx context.Context, cmd *cli.Command) error {
							member, err := requireMember(cmd)
							if err != nil {
								return err
							}
							fmt.Printf("Removed %s from the team\n", member)
							return nil
						},
					},
				},
			},
		},
	}

	// Run returns the first non-nil error from any handler. Usage errors
	// (unknown flags, missing args) are already printed by cli itself, so we
	// only echo unexpected errors to stderr and exit non-zero.
	if err := cmd.Run(context.Background(), os.Args); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

// requireMember returns the single positional member name, or a cli.Exit
// error explaining the expected usage. Shared by `team add` and `team remove`
// so both Actions stay one-liners and the error message stays consistent.
func requireMember(cmd *cli.Command) (string, error) {
	args := cmd.Args()
	if args.Len() != 1 {
		return "", cli.Exit(fmt.Sprintf("team %s requires exactly one member name", cmd.Name), 2)
	}
	return args.First(), nil
}

// requireNoArgs rejects unexpected positionals on commands that take none
// (`hello`/`bye`). Keeps arg handling consistent with `team`'s strictness.
func requireNoArgs(cmd *cli.Command) error {
	if cmd.Args().Len() > 0 {
		return cli.Exit(fmt.Sprintf("%s takes no arguments", cmd.Name), 2)
	}
	return nil
}

// requireName rejects an explicitly empty --name value. The flag defaults to
// "World", so an empty value means the user passed `--name ""` — reject it
// instead of printing "Hello, !".
func requireName(name string) error {
	if name == "" {
		return cli.Exit("--name must not be empty", 2)
	}
	return nil
}

// sayHello and sayBye are shared helpers so each Action stays tiny.
func sayHello(name string) error {
	if err := requireName(name); err != nil {
		return err
	}
	fmt.Printf("Hello, %s!\n", name)
	return nil
}

func sayBye(name string) error {
	if err := requireName(name); err != nil {
		return err
	}
	fmt.Printf("Goodbye, %s!\n", name)
	return nil
}
