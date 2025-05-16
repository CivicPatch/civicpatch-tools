package main

import (
	"civpatch/commands"
	"context"
	"flag"
	"fmt"
	"os"
	"strings"
)

var (
	scrapeCommand = flag.NewFlagSet("scrape", flag.ExitOnError)
	state         = scrapeCommand.String("state", "", "State to scrape")

	scrapePlan   = scrapeCommand.Bool("plan", false, "Plan the scrapes")
	numScrapes   = scrapeCommand.Int("num-scrapes", 1, "Number of scrapes to plan")
	gnisToIgnore = scrapeCommand.String("gnis-to-ignore", "", "GNIS IDs to ignore")

	scrapeRun = scrapeCommand.Bool("run", false, "Run the scrapes")
	createPr  = scrapeCommand.Bool("create-pr", false, "Create a PR")
	develop   = scrapeCommand.Bool("develop", false, "Develop locally")
	gnis      = scrapeCommand.String("gnis", "", "GNIS ID to scrape")
	withCi    = scrapeCommand.Bool("with-ci", false, "Run with CI")

	// authClear = flag.NewFlagSet("auth-clear", flag.ExitOnError)
	// geoid         = scrapeCommand.String("geoid", "", "GEOID to scrape") TODO: FIX
)

func scrapeCommands(ctx context.Context, scrapePlan bool, scrapeRun bool) error {
	var output string
	var err error

	if scrapePlan {
		output, err = commands.ScrapePlan(*state, *numScrapes, strings.Split(*gnisToIgnore, ","))
		if err != nil {
			return err
		}
	}
	if scrapeRun {
		err = commands.ScrapeRun(ctx, *state, *gnis, *createPr, *develop, *withCi)
		if err != nil {
			return err
		}
	}

	if output != "" {
		fmt.Println(output)
	}
	return nil
}

func main() {
	ctx := context.Background()
	args := os.Args[1:]
	if len(args) == 0 {
		fmt.Println("Usage: civpatch <command> [options]")
		os.Exit(1)
	}

	switch args[0] {
	case "scrape":
		scrapeCommand.Parse(args[1:])
		if err := scrapeCommands(ctx, *scrapePlan, *scrapeRun); err != nil {
			handleError(err)
		}
	case "deploy":
		commands.Deploy(ctx)
	case "auth-clear":
		commands.AuthClear()
	}
}

func handleError(err error) {
	fmt.Println(err)
	os.Exit(1)
}
