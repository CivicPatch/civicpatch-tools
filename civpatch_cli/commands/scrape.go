package commands

import (
	"civpatch/docker"
	"civpatch/utils"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math/rand"
	"net/http"
	"os"
	"slices"
	"strings"
)

const (
	DATA_SOURCE_URL = "https://raw.githubusercontent.com/CivicPatch/civicpatch-tools/refs/heads/main/civpatch/data_source/<STATE>/municipalities.json"

	hostOutputDir = "."
)

type Municipality struct {
	Name        string   `json:"name"`
	Geoid       string   `json:"geoid"`
	Website     string   `json:"website"`
	MetaSources []string `json:"meta_sources"`
}

type MunicipalityResponse struct {
	Data []Municipality `json:"municipalities"`
}

func ScrapePlan(state string, numMunicipalities int, geoidsToIgnore []string) (string, error) {
	err := checkPlanInput(state)
	if err != nil {
		return "", err
	}

	municipalities, err := loadMunicipalities(state)
	if err != nil {
		return "", err
	}

	selected := selectMunicipalities(municipalities, numMunicipalities, geoidsToIgnore)

	jsonData, err := json.Marshal(selected)
	if err != nil {
		return "", err
	}

	return string(jsonData), nil
}

func ScrapeRun(ctx context.Context, state string, geoid string, createPr bool, develop bool, withCi bool, sendCosts bool, branchName string, githubEnv string, prNumber int) error {
	if state == "" {
		return fmt.Errorf("error: state is required")
	}
	if geoid == "" {
		return fmt.Errorf("error: geoid is required")
	}

	if prNumber != 0 && createPr {
		return fmt.Errorf("error: cannot create a PR and update an existing PR at the same time")
	}

	if prNumber != 0 && branchName == "" {
		return fmt.Errorf("error: cannot update an existing PR without providing a branch name")
	}

	requiredEnvVars, err := checkScrapeEnvs(state, geoid, withCi, sendCosts)
	if err != nil {
		return err
	}

	dockerClient, err := prepareScrape(ctx, develop)
	if err != nil {
		return err
	}
	defer dockerClient.Close()

	fmt.Printf("Scraping %s %s with createPr: %t, develop: %t, withCi: %t, sendCosts: %t, branchName: %s, githubEnv: %s, prNumber: %d\n", state, geoid, createPr, develop, withCi, sendCosts, branchName, githubEnv, prNumber)

	envVars := map[string]string{}

	for _, envVar := range requiredEnvVars {
		envVars[envVar] = os.Getenv(envVar)
	}

	// Note: these are usually set by the Github Actions pipeline
	if branchName == "" { // Only populated if updating existing PR
		runId := fmt.Sprintf("%d", rand.Intn(1000000))
		branchName = fmt.Sprintf("pipeline-municipal-scrapes-%s-%s-%s", state, geoid, runId)
	}
	envVars["BRANCH_NAME"] = branchName

	if prNumber != 0 { // Only populated if updating existing PR
		envVars["PR_NUMBER"] = fmt.Sprintf("%d", prNumber)
	}
	if githubEnv != "" { // Determines what env shell we should use
		envVars["GITHUB_ENV"] = githubEnv
	}

	cmd := []string{
		"./lib/tasks/scripts/checkout_branch.sh",
		"&&",
		fmt.Sprintf("xvfb-run rake 'pipeline:scrape[%s,%s,%t]'", state, geoid, createPr),
	}

	output := docker.TaskOptionsOutput{
		StreamOutput: true,
	}

	fmt.Printf("Starting scrape job. This might take a while...")
	if createPr {
		cmd = append(cmd, "&&", fmt.Sprintf("./lib/tasks/scripts/create_pull_request.sh %s %s", state, geoid))
	} else {
		fmt.Printf("Check out the logs for the container in Docker Desktop (if available).\n")
		output = docker.TaskOptionsOutput{
			StreamOutput:    false,
			CopyOutputFrom:  []string{"/app/output"},
			CopyOutputToDir: hostOutputDir,
		}
	}

	_, err = dockerClient.RunTask(ctx, docker.TaskOptions{
		EnvVars: envVars,
		Command: strings.Join(cmd, " "),
		Develop: develop,
		Output:  output,
	})

	if err != nil {
		if ctx.Err() != nil {
			return fmt.Errorf("task timed out: %w", err)
		}
		return fmt.Errorf("task failed: %w", err)
	}

	return nil
}

func loadMunicipalities(state string) ([]Municipality, error) {
	uri := strings.Replace(DATA_SOURCE_URL, "<STATE>", state, 1)

	response, err := http.Get(uri)
	if err != nil {
		return nil, fmt.Errorf("error fetching data: %w", err)
	}
	defer response.Body.Close()

	byteValue, err := io.ReadAll(response.Body)
	if err != nil {
		return nil, fmt.Errorf("error reading file: %w", err)
	}

	var municipalities MunicipalityResponse

	err = json.Unmarshal(byteValue, &municipalities)
	if err != nil {
		return nil, fmt.Errorf("error unmarshalling file: %w", err)
	}

	return municipalities.Data, nil
}

func selectMunicipalities(municipalities []Municipality, numMunicipalities int, geoidsToIgnore []string) []Municipality {
	municipalitiesToScrape := []Municipality{}

	for _, municipality := range municipalities {
		if shouldScrape(geoidsToIgnore, municipality) {
			municipalitiesToScrape = append(municipalitiesToScrape, municipality)
		}
		if len(municipalitiesToScrape) >= numMunicipalities {
			break
		}
	}
	return municipalitiesToScrape
}

func checkPlanInput(state string) error {
	if len(state) == 0 {
		return fmt.Errorf("error: state is required")
	}
	return nil
}

func shouldScrape(geoidsToIgnore []string, municipality Municipality) bool {
	return !slices.Contains(geoidsToIgnore, municipality.Geoid) &&
		len(municipality.Geoid) > 0 &&
		len(municipality.Website) > 0 &&
		(len(municipality.MetaSources) == 0 || len(municipality.MetaSources) == 1)
}

func checkScrapeEnvs(state string, geoid string, withCI bool, sendCosts bool) ([]string, error) {
	requiredEnvVars := utils.RequiredScrapeEnvVars
	if sendCosts {
		requiredEnvVars = append(requiredEnvVars, utils.RequiredEnvVarsSendCosts...)
	}
	if withCI {
		requiredEnvVars = append(requiredEnvVars, utils.RequiredEnvVarsCI...)
	}

	err := utils.CheckEnvironmentVariables(requiredEnvVars)
	allEnvVars := append(requiredEnvVars, utils.RequiredEnvVarsCI...)

	if err != nil {
		return nil, err
	}

	if len(state) == 0 {
		return nil, fmt.Errorf("error: state is required")
	}
	if len(geoid) == 0 {
		return nil, fmt.Errorf("error: geoid is required")
	}

	return allEnvVars, nil
}

func prepareScrape(ctx context.Context, develop bool) (*docker.Client, error) {
	dockerClient, err := docker.NewClient()
	if err != nil {
		return nil, fmt.Errorf("error creating docker client: %w", err)
	}

	dockerClient.PrepareContainer(ctx, develop)

	return dockerClient, nil
}
