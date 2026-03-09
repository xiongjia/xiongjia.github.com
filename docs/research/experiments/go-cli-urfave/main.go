package main

import (
	"fmt"
	"log"
	"os"

	"github.com/urfave/cli/v2"
)

func main() {
	app := &cli.App{
		Name:  "greet",
		Usage: "a simple CLI to learn urfave/cli",
		Flags: []cli.Flag{
			&cli.StringFlag{
				Name:  "name",
				Usage: "name to greet",
				Value: "World",
			},
		},
		Action: func(c *cli.Context) error {
			fmt.Printf("Hello, %s!\n", c.String("name"))
			return nil
		},
	}

	if err := app.Run(os.Args); err != nil {
		log.Fatal(err)
	}
}
