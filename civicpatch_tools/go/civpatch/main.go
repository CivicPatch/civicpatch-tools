package main

import (
	"bufio"
	"context"
	"flag"
	"fmt"
	"os"

	"civpatch/docker"
	"civpatch/services"
)

var (
	GITHUB_CLIENT_ID = "Iv23liEGI2vDgAHmft8C"
	scrapeCommand    = flag.NewFlagSet("scrape", flag.ExitOnError)
	withCI           = scrapeCommand.Bool("with-ci", false, "Run with CI")
	dryRun           = scrapeCommand.Bool("dry-run", true, "Run scraper, but don't open a PR")
	state            = scrapeCommand.String("state", "", "State to scrape")
	gnis             = scrapeCommand.String("gnis", "", "GNIS ID to scrape")
	// geoid         = scrapeCommand.String("geoid", "", "GEOID to scrape") TODO: FIX
)

func checkGitHubCredentials(ctx context.Context) {
	deviceFlow, err := services.NewGitHubDeviceFlow(GITHUB_CLIENT_ID)
	if err != nil {
		fmt.Println("Error creating device flow:", err)
		os.Exit(1)
	}

	client, err := deviceFlow.NewClient(ctx)
	if err != nil {
		fmt.Println("Error getting GitHub Client", err)
		os.Exit(1)
	}

	user, _, err := client.Users.Get(ctx, "")
	if err != nil {
		fmt.Println("Error getting user:", err)
		os.Exit(1)
	}

	fmt.Printf("Successfully authenticated as %s\n", *user.Name)
}

func checkScrapeInput(ctx context.Context, state string, gnis string, withCI bool) {
	if withCI {
		checkEnvironmentVariables(requiredEnvVarsCI)
	} else {
		checkEnvironmentVariables(requiredEnvVars)
		checkGitHubCredentials(ctx)
	}

	if state == "" {
		fmt.Println("Error: state is required")
		os.Exit(1)
	}
	if gnis == "" {
		fmt.Println("Error: gnis is required")
		os.Exit(1)
	}
}

func scrape(state string, gnis string, dryRun bool, withCI bool) error {
	ctx := context.Background()
	checkScrapeInput(ctx, state, gnis, withCI)

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

	containerID, logs, logCancel, err := dockerClient.RunContainer(ctx, "scraper:local", requiredEnvVars,
		cmd,
		volumes)
	if err != nil {
		fmt.Println("Error running container:", err)
		os.Exit(1)
	}

	defer logCancel()

	fmt.Println("Container started:", containerID)

	// Set stdout and stderr to unbuffered
	//os.Stdout = os.NewFile(1, "stdout")
	//os.Stderr = os.NewFile(2, "stderr")

	scanner := bufio.NewScanner(logs)
	for scanner.Scan() {
		fmt.Println(scanner.Text())
	}

	//_, err = stdcopy.StdCopy(os.Stdout, os.Stderr, logs)
	//if err != nil {
	//	fmt.Println("Error copying logs:", err)
	//}
	//return nil
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
		scrape(*state, *gnis, *dryRun, *withCI)
	}
}
