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
	// ================================ Scrape Commands ================================
	scrapeCommand = flag.NewFlagSet("scrape", flag.ExitOnError)
	state         = scrapeCommand.String("state", "", "State to scrape")

	// =================== Scrape Plan Commands ===================
	// -state: required
	// -num-scrapes: optional
	// -geoids-to-ignore: optional
	scrapePlan     = scrapeCommand.Bool("plan", false, "Plan the scrapes")
	numScrapes     = scrapeCommand.Int("num-scrapes", 1, "Number of scrapes to plan")
	geoidsToIgnore = scrapeCommand.String("geoids-to-ignore", "", "Optional: GEOIDs to ignore (comma-separated list)")

	// =================== Scrape Run Commands ===================
	// -state: required
	// -geoid: required
	// -branch-name: optional, for updating existing PRs
	// -pr-number: optional, for updating existing PRs
	// -create-pr: optional
	// -send-costs: optional, for recording costs with Google Sheets
	// -with-ci: optional TODO remove this, don't care about github token retrieval via Device flow
	// -github-env: only for CivicPatch-run pipelines
	// -develop: optional
	scrapeRun   = scrapeCommand.Bool("run", false, "Run the scrapes")
	scrapeGeoid = scrapeCommand.String("geoid", "", "GEOID to scrape")
	createPr    = scrapeCommand.Bool("create-pr", false, "Create a PR")

	branchName = scrapeCommand.String("branch-name", "", "Branch name")
	prNumber   = scrapeCommand.Int("pr-number", 0, "PR number")

	sendCosts = scrapeCommand.Bool("send-costs", false, "Send costs to Google Sheets")
	withCi    = scrapeCommand.Bool("with-ci", false, "Run with CI - noninteractive")

	githubEnv = scrapeCommand.String("github-env", "", "Github environment")
	develop   = scrapeCommand.Bool("develop", false, "Develop locally")

	// ================================ Run Task Commands ================================
	runTask        = flag.NewFlagSet("run-task", flag.ExitOnError)
	runTaskBranch  = runTask.String("branch-name", "", "Branch name")
	runTaskCommand = runTask.String("command", "", "Task to run")
	runTaskDevelop = runTask.Bool("develop", false, "Develop locally") // Optional -- only needed if testing changes locally

	// ================================ Misc Commands ================================
	cleanupCommand = flag.NewFlagSet("cleanup", flag.ExitOnError)
	containerId    = cleanupCommand.String("container-id", "", "Container ID") // Leave blank to remove all civicpatch tagged containers
)

func scrapeCommands(ctx context.Context, scrapePlan bool, scrapeRun bool) error {
	var output string
	var err error

	if scrapePlan {
		output, err = commands.ScrapePlan(*state, *numScrapes, strings.Split(*geoidsToIgnore, ","))
		if err != nil {
			return err
		}
	} else if scrapeRun {
		err = commands.ScrapeRun(ctx, *state, *scrapeGeoid, *createPr, *develop, *withCi, *sendCosts, *branchName, *githubEnv, *prNumber)
		if err != nil {
			return err
		}
	} else {
		return fmt.Errorf("no scrape sub-command provided")
	}

	if output != "" {
		fmt.Println(output)
	}
	return nil
}

func runTaskCommands(ctx context.Context) error {
	output, err := commands.RunTask(ctx,
		*runTaskBranch,
		*runTaskCommand,
		*runTaskDevelop,
	)
	if err != nil {
		return err
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
	case "run-task":
		runTask.Parse(args[1:])
		err := runTaskCommands(ctx)
		if err != nil {
			handleError(err)
		}
	case "auth-clear":
		commands.AuthClear()
	case "cleanup":
		cleanupCommand.Parse(args[1:])
		commands.CleanupContainers(ctx, *containerId)
	}
}

func handleError(err error) {
	fmt.Println(err)
	os.Exit(1)
}
