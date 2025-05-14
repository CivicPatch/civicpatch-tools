package main

import (
	"context"
	"flag"
	"fmt"
	"os"

	"civpatch/docker"

	"github.com/docker/docker/pkg/stdcopy"
)

var (
	scrapeCommand = flag.NewFlagSet("scrape", flag.ExitOnError)
	dryRun        = scrapeCommand.Bool("dry-run", true, "Run scraper, but don't open a PR")
	state         = scrapeCommand.String("state", "", "State to scrape")
	gnis          = scrapeCommand.String("gnis", "", "GNIS ID to scrape")
	// geoid         = scrapeCommand.String("geoid", "", "GEOID to scrape") TODO: FIX

	requiredEnvVars = []string{
		"OPENAI_TOKEN",
		"BRAVE_TOKEN",
		"GOOGLE_GEMINI_TOKEN",
		"CLOUDFLARE_R2_ENDPOINT", // TODO: Get rid of this
		"CLOUDFLARE_R2_ACCESS_KEY_ID",
		"CLOUDFLARE_R2_SECRET_KEY",
		"GOOGLE_SEARCH_API_KEY",
		"GOOGLE_SEARCH_ENGINE_ID",
	}
)

func checkEnvironmentVariables() {
	for _, envVar := range requiredEnvVars {
		if os.Getenv(envVar) == "" {
			fmt.Printf("Error: %s is not set\n", envVar)
			os.Exit(1)
		}
	}
}

func checkScrapeInput(state string, gnis string) {
	checkEnvironmentVariables()
	if state == "" {
		fmt.Println("Error: state is required")
		os.Exit(1)
	}
	if gnis == "" {
		fmt.Println("Error: gnis is required")
		os.Exit(1)
	}
}

func scrape(state string, gnis string, dryRun bool) error {
	ctx := context.Background()
	checkScrapeInput(state, gnis)

	fmt.Println("Scraping with dry run:", dryRun)

	dockerClient, err := docker.NewClient()
	if err != nil {
		fmt.Println("Error creating docker client:", err)
		os.Exit(1)
	}
	defer dockerClient.Close()

	if err := dockerClient.BuildImage(ctx, "Dockerfile", "scraper:local"); err != nil {
		fmt.Println("Error building image:", err)
		os.Exit(1)
	}

	volumes := map[string]string{
		"./config": "/app/config",
		"./lib":    "/app/lib",
	}

	cmd := []string{"rake", fmt.Sprintf("pipeline:fetch[%s,%s,%t]", state, gnis, dryRun)}

	containerID, logs, err := dockerClient.RunContainer(ctx, "scraper:local", requiredEnvVars,
		cmd,
		volumes)
	if err != nil {
		fmt.Println("Error running container:", err)
		os.Exit(1)
	}
	defer logs.Close()

	fmt.Println("Container started:", containerID)

	// Set stdout and stderr to unbuffered
	os.Stdout = os.NewFile(1, "stdout")
	os.Stderr = os.NewFile(2, "stderr")

	_, err = stdcopy.StdCopy(os.Stdout, os.Stderr, logs)
	if err != nil {
		fmt.Println("Error copying logs:", err)
	}
	return nil
}

func main() {
	args := os.Args[1:]
	if len(args) == 0 {
		fmt.Println("Usage: civpatch <command> [options]")
		os.Exit(1)
	}

	switch args[0] {
	case "scrape":
		scrapeCommand.Parse(args[1:])
	}

	if scrapeCommand.Parsed() {
		scrape(*state, *gnis, *dryRun)
	}
}
