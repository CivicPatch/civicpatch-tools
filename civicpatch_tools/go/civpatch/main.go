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
	withCi           = scrapeCommand.Bool("with-ci", false, "Run with CI")
	createPr         = scrapeCommand.Bool("create-pr", false, "Create a PR")
	develop          = scrapeCommand.Bool("develop", false, "Develop locally")
	state            = scrapeCommand.String("state", "", "State to scrape")
	gnis             = scrapeCommand.String("gnis", "", "GNIS ID to scrape")
	// geoid         = scrapeCommand.String("geoid", "", "GEOID to scrape") TODO: FIX
	municipalities = flag.NewFlagSet("municipalities", flag.ExitOnError)
)

func checkGitHubCredentials(ctx context.Context) string {
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

	github_token, err := deviceFlow.GetToken(ctx)
	if err != nil {
		fmt.Println("Error getting GitHub token:", err)
		os.Exit(1)
	}

	return github_token.AccessToken
}

func checkScrapeInput(state string, gnis string, withCI bool) {
	if withCI {
		checkEnvironmentVariables(requiredEnvVarsCI)
	} else {
		checkEnvironmentVariables(requiredEnvVars)
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

func scrape(state string, gnis string, createPr bool, withCi bool, develop bool) error {
	ctx := context.Background()
	checkScrapeInput(state, gnis, withCi)

	github_token := os.Getenv("GITHUB_TOKEN")
	if !withCi {
		github_token = checkGitHubCredentials(ctx)
	}

	fmt.Printf("Scraping with createPr: %t\n", createPr)

	dockerClient, err := docker.NewClient()
	if err != nil {
		fmt.Println("Error creating docker client:", err)
		os.Exit(1)
	}
	defer dockerClient.Close()

	imageTag := "civpatch"
	dockerfile := "Dockerfile.civpatch"
	if develop {
		imageTag = "civpatch-dev"
		dockerfile = "Dockerfile.civpatch-dev"
	}

	if err := dockerClient.BuildImage(ctx, dockerfile, imageTag); err != nil {
		fmt.Println("Error building image:", err)
		os.Exit(1)
	}

	volumes := map[string]string{}
	if develop {
		volumes = map[string]string{
			"./config": "/app/config",
			"./lib":    "/app/lib",
		}
	}

	args := map[string]string{
		"GITHUB_TOKEN": github_token,
	}

	cmd := []string{"rake", fmt.Sprintf("pipeline:fetch[%s,%s,%t]", state, gnis, createPr)}

	containerID, logs, logCancel, err := dockerClient.RunContainer(ctx,
		imageTag,
		requiredEnvVarsCI,
		args,
		cmd,
		volumes)
	if err != nil {
		fmt.Println("Error running container:", err)
		os.Exit(1)
	}

	defer logCancel()

	fmt.Println("Container started:", containerID)

	scanner := bufio.NewScanner(logs)
	for scanner.Scan() {
		fmt.Println(scanner.Text())
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
		scrape(*state, *gnis, *createPr, *withCi, *develop)
	}
}
