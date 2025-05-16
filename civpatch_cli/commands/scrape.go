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
	"slices"
	"strings"
)

const (
	DATA_SOURCE_URL = "https://raw.githubusercontent.com/CivicPatch/open-data/refs/heads/main/data_source/<STATE>/municipalities.json"
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

func ScrapeRun(ctx context.Context, state string, gnis string, createPr bool, develop bool, withCi bool) error {
	githubUsername, githubToken, dockerClient, err := prepareScrape(ctx, state, gnis, withCi, develop)
	if err != nil {
		return err
	}
	defer dockerClient.Close()

	fmt.Printf("Scraping with createPr: %t\n", createPr)

	if develop {
	}

	args := map[string]string{
		"GITHUB_TOKEN":    githubToken,
		"GITHUB_USERNAME": githubUsername,
	}

	imageTag := remoteImageTag
	cmd := []string{}
	volumes := map[string]string{}
	if develop {
		imageTag = localImageTag
		cmd = []string{"rake", fmt.Sprintf("pipeline:fetch[%s,%s,%t,%t]", state, gnis, develop, createPr)}
		volumes = map[string]string{
			".": "/app",
		}
	} else {
		cmd = []string{
			"rake", fmt.Sprintf("pipeline:fetch[%s,%s,%t,%t]", state, gnis, develop, createPr),
		}
	}

	containerID, logs, logCancel, err := dockerClient.RunContainer(ctx,
		imageTag,
		utils.RequiredEnvVarsCI,
		args,
		cmd,
		volumes)
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

func checkScrapeInput(state string, gnis string, withCI bool) error {
	if withCI {
		err := utils.CheckEnvironmentVariables(utils.RequiredEnvVarsCI)
		if err != nil {
			return err
		}
	} else {
		err := utils.CheckEnvironmentVariables(utils.RequiredEnvVars)
		if err != nil {
			return err
		}
	}

	if len(state) == 0 {
		return fmt.Errorf("error: state is required")
	}
	if len(gnis) == 0 {
		return fmt.Errorf("error: gnis is required")
	}

	return nil
}

func prepareScrape(ctx context.Context, state string, gnis string, withCi bool, develop bool) (string, string, *docker.Client, error) {
	err := checkScrapeInput(state, gnis, withCi)
	if err != nil {
		return "", "", nil, err
	}

	githubUsername, githubToken, err := services.CheckGithubCredentials(ctx)
	if err != nil {
		return "", "", nil, err
	}

	dockerClient, err := docker.NewClient()
	if err != nil {
		return "", "", nil, fmt.Errorf("error creating docker client: %w", err)
	}

	if develop {
		if err := dockerClient.BuildImage(ctx, "Dockerfile.civpatch", localImageTag); err != nil {
			return "", "", nil, fmt.Errorf("error building image: %w", err)
		}
	} else {
		fmt.Println("Pulling image:", remoteImageTag)
		if err := dockerClient.PullImage(ctx, remoteImageTag, githubUsername, githubToken); err != nil {
			return "", "", nil, fmt.Errorf("error pulling image: %w", err)
		}
	}

	return githubUsername, githubToken, dockerClient, nil
}
