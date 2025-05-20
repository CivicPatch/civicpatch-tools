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
	"net/http"
	"os"
	"os/exec"
	"slices"
	"strings"
)

const (
	DATA_SOURCE_URL = "https://raw.githubusercontent.com/CivicPatch/civicpatch-tools/refs/heads/main/civpatch/data_source/<STATE>/municipalities.json"

	imageName       = "ghcr.io/civicpatch/civpatch"
	localImageTag   = "develop"
	remoteImageTag  = "latest"
	localImageName  = imageName + ":" + localImageTag
	remoteImageName = imageName + ":" + remoteImageTag
)

type Municipality struct {
	Name        string   `json:"name"`
	GNIS        string   `json:"gnis"`
	Website     string   `json:"website"`
	MetaSources []string `json:"meta_sources"`
}

type MunicipalityResponse struct {
	Data []Municipality `json:"municipalities"`
}

func ScrapePlan(state string, numMunicipalities int, gnisToIgnore []string) (string, error) {
	err := checkPlanInput(state)
	if err != nil {
		return "", err
	}

	municipalities, err := loadMunicipalities(state)
	if err != nil {
		return "", err
	}

	selected := selectMunicipalities(municipalities, numMunicipalities, gnisToIgnore)

	jsonData, err := json.Marshal(selected)
	if err != nil {
		return "", err
	}

	return string(jsonData), nil
}

func ScrapeRun(ctx context.Context, state string, gnis string, createPr bool, develop bool, withCi bool, sendCosts bool, branchName string, githubEnv string, prNumber int) error {
	if state == "" {
		return fmt.Errorf("error: state is required")
	}
	if gnis == "" {
		return fmt.Errorf("error: gnis is required")
	}

	if prNumber != 0 && createPr {
		return fmt.Errorf("error: cannot create a PR and update an existing PR at the same time")
	}

	if prNumber != 0 && branchName == "" {
		return fmt.Errorf("error: cannot update an existing PR without providing a branch name")
	}

	requiredEnvVars, err := checkScrapeEnvs(state, gnis, withCi, sendCosts)
	if err != nil {
		return err
	}

	githubUsername, githubToken, dockerClient, err := prepareScrape(ctx, develop)
	if err != nil {
		return err
	}
	defer dockerClient.Close()

	fmt.Printf("Scraping %s %s with createPr: %t\n", state, gnis, createPr)

	envVars := map[string]string{}

	for _, envVar := range requiredEnvVars {
		envVars[envVar] = os.Getenv(envVar)
	}
	envVars["GITHUB_TOKEN"] = githubToken
	envVars["GITHUB_USERNAME"] = githubUsername

	// Note: these are usually set by the Github Actions pipeline
	if branchName != "" {
		envVars["BRANCH_NAME"] = branchName
	}
	if githubEnv != "" { // Determines what env shell we should use
		envVars["GITHUB_ENV"] = githubEnv
	}
	if prNumber != 0 {
		envVars["PR_NUMBER"] = fmt.Sprintf("%d", prNumber)
	}

	cmd := []string{
		"./lib/tasks/scripts/checkout_scrape_branch.sh",
		state,
		gnis,
		"&&",
		"rake",
		fmt.Sprintf("pipeline:fetch[%s,%s,%t,%t]", state, gnis, createPr, sendCosts),
	}

	volumes := map[string]string{}
	fullImageName := remoteImageName

	if develop {
		fullImageName = localImageName
		volumes = map[string]string{
			"./civpatch/lib": "/app/civpatch/lib",
		}
	}

	fmt.Println("Running container with image:", fullImageName)
	labels := map[string]string{
		"state": state, // Assumption: we only run one container for state + gnis at a time
		"gnis":  gnis,
	}

	containerID, logs, logCancel, err := dockerClient.RunContainer(ctx,
		fullImageName,
		envVars,
		cmd,
		volumes,
		labels)
	if err != nil {
		return fmt.Errorf("error running container: %w", err)
	}

	defer logCancel()

	fmt.Println("Container started:", containerID)

	scanner := bufio.NewScanner(logs)
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

func selectMunicipalities(municipalities []Municipality, numMunicipalities int, gnisToIgnore []string) []Municipality {
	municipalitiesToScrape := []Municipality{}

	for _, municipality := range municipalities {
		if shouldScrape(gnisToIgnore, municipality) {
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

func shouldScrape(gnisToIgnore []string, municipality Municipality) bool {
	return !slices.Contains(gnisToIgnore, municipality.GNIS) &&
		len(municipality.GNIS) > 0 &&
		len(municipality.Website) > 0 &&
		(len(municipality.MetaSources) == 0 || len(municipality.MetaSources) == 1)
}

func checkScrapeEnvs(state string, gnis string, withCI bool, sendCosts bool) ([]string, error) {
	requiredEnvVars := utils.RequiredEnvVars
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
	if len(gnis) == 0 {
		return nil, fmt.Errorf("error: gnis is required")
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

	if develop {
		fmt.Println("Building image:", localImageName)
		scriptPath, err := utils.FromProjectRoot("civpatch/build.sh")
		if err != nil {
			return "", "", nil, fmt.Errorf("error getting script path: %w", err)
		}

		cmd := exec.Command("bash", scriptPath)
		currentEnv := os.Environ()
		cmd.Env = append(currentEnv,
			"IMAGE_NAME="+imageName,
			"RELEASE_VERSION="+localImageTag,
		)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr

		fmt.Println("Finished running script")
		if err := cmd.Run(); err != nil {
			return "", "", nil, fmt.Errorf("error running script: %w", err)
		}
	} else {
		fmt.Println("Pulling image:", remoteImageName)
		if err := dockerClient.PullImage(ctx, remoteImageName, githubUsername, githubToken); err != nil {
			return "", "", nil, fmt.Errorf("error pulling image: %w", err)
		}
	}

	return githubUsername, githubToken, dockerClient, nil
}
