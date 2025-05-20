package commands

import (
	"bufio"
	"civpatch/docker"
	"civpatch/services"
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
	"time"
)

const (
	DATA_SOURCE_URL = "https://raw.githubusercontent.com/CivicPatch/civicpatch-tools/refs/heads/main/civpatch/data_source/<STATE>/municipalities.json"
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

	githubUsername, githubToken, dockerClient, err := prepareScrape(ctx, develop)
	if err != nil {
		return err
	}
	defer dockerClient.Close()

	fmt.Printf("Scraping %s %s with createPr: %t, develop: %t, withCi: %t, sendCosts: %t, branchName: %s, githubEnv: %s, prNumber: %d\n", state, geoid, createPr, develop, withCi, sendCosts, branchName, githubEnv, prNumber)

	envVars := map[string]string{}

	for _, envVar := range requiredEnvVars {
		envVars[envVar] = os.Getenv(envVar)
	}
	envVars["GITHUB_TOKEN"] = githubToken
	envVars["GITHUB_USERNAME"] = githubUsername

	// Note: these are usually set by the Github Actions pipeline
	if branchName != "" { // Only populated if updating existing PR
		envVars["BRANCH_NAME"] = branchName
	} else {
		runId := fmt.Sprintf("%d", rand.Intn(1000000))
		envVars["BRANCH_NAME"] = fmt.Sprintf("pipeline-municipal-scrapes-%s-%s-%s", state, geoid, runId)
	}

	if prNumber != 0 { // Only populated if updating existing PR
		envVars["PR_NUMBER"] = fmt.Sprintf("%d", prNumber)
	}
	if githubEnv != "" { // Determines what env shell we should use
		envVars["GITHUB_ENV"] = githubEnv
	}

	cmd := []string{
		"./lib/tasks/scripts/checkout_branch.sh",
		"&&",
		fmt.Sprintf("rake 'pipeline:fetch[%s,%s,%t,%t]'", state, geoid, createPr, sendCosts),
	}

	labels := map[string]string{
		"state": state, // Assumption: we only run one container for state + geoid at a time
		"geoid": geoid,
	}

	taskResult, err := dockerClient.RunTask(ctx, docker.TaskOptions{
		EnvVars:      envVars,
		Command:      strings.Join(cmd, " "),
		Labels:       labels,
		Timeout:      10 * time.Minute,
		StreamOutput: true,
	})
	if err != nil {
		return fmt.Errorf("error running container: %w", err)
	}

	defer taskResult.Cancel()

	fmt.Println("Container started:", taskResult.ContainerId)

	scanner := bufio.NewScanner(taskResult.Logs)
	for scanner.Scan() {
		fmt.Println(scanner.Text())
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
	if err != nil {
		return nil, err
	}

	if len(state) == 0 {
		return nil, fmt.Errorf("error: state is required")
	}
	if len(geoid) == 0 {
		return nil, fmt.Errorf("error: geoid is required")
	}

	return requiredEnvVars, nil
}

func prepareScrape(ctx context.Context, develop bool) (string, string, *docker.Client, error) {
	githubUsername, githubToken, err := services.GetGithubCredentials(ctx)
	if err != nil {
		return "", "", nil, err
	}

	dockerClient, err := docker.NewClient()
	if err != nil {
		return "", "", nil, fmt.Errorf("error creating docker client: %w", err)
	}

	dockerClient.PrepareContainer(ctx, develop)

	return githubUsername, githubToken, dockerClient, nil
}
