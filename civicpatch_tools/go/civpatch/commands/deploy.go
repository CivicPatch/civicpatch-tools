package commands

import (
	"civpatch/docker"
	"civpatch/utils"
	"context"
	"fmt"
	"os"
)

const (
	localImageTag  = "civpatch"
	remoteImageTag = "ghcr.io/civicpatch/civpatch"
)

// To generate GITHUB_TOKEN for development, run:
// gh auth login --scopes "write:packages"
// gh auth token
// Set GITHUB_TOKEN and GITHUB_USERNAME in your environment
func Deploy(ctx context.Context) error {
	err := utils.CheckEnvironmentVariables(utils.RequiredEnvVarsDeploy)
	if err != nil {
		return err
	}

	githubToken, githubUsername, err := checkDeployInput()
	if err != nil {
		return err
	}

	dockerClient, err := docker.NewClient()
	if err != nil {
		return err
	}
	defer dockerClient.Close()

	if err := dockerClient.BuildImage(ctx, "Dockerfile.civpatch", remoteImageTag); err != nil {
		return fmt.Errorf("error building image: %w", err)
	}

	if err := dockerClient.PushImage(ctx, remoteImageTag, githubUsername, githubToken); err != nil {
		return fmt.Errorf("error pushing image: %w", err)
	}

	return nil
}

func checkDeployInput() (string, string, error) {
	if os.Getenv("GITHUB_TOKEN") == "" {
		return "", "", fmt.Errorf("GITHUB_TOKEN should be set with following scopes: %v", []string{"write:packages"})
	}

	if os.Getenv("GITHUB_USERNAME") == "" {
		return "", "", fmt.Errorf("GITHUB_USERNAME should be set")
	}

	return os.Getenv("GITHUB_TOKEN"), os.Getenv("GITHUB_USERNAME"), nil
}
