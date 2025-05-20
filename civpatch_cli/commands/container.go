package commands

import (
	"civpatch/docker"
	"civpatch/services"
	"context"
	"fmt"
	"strings"
)

func CleanupContainers(ctx context.Context, containerId string) error {
	dockerClient, err := docker.NewClient()
	if err != nil {
		return fmt.Errorf("error creating docker client: %v", err)
	}

	containerIds := []string{}

	if containerId == "" {
		containers, err := dockerClient.ListContainers(ctx)
		if err != nil {
			return fmt.Errorf("error listing containers: %v", err)
		}
		for _, container := range containers {
			containerIds = append(containerIds, container.ID)
		}
	} else {
		containerIds = append(containerIds, containerId)
	}

	for _, containerId := range containerIds {
		fmt.Printf("container: Stopping and removing %s\n", containerId)
		err := dockerClient.CleanupContainer(ctx, containerId)
		if err != nil {
			return fmt.Errorf("error stopping container: %v", err)
		}
	}
	return nil
}

func RunRakeTask(ctx context.Context,
	state string,
	geoid string,
	command string,
	branchName string,
	develop bool,
) (string, error) {
	if state == "" || geoid == "" || command == "" {
		return "", fmt.Errorf("error: state, geoid, and command are required")
	}

	dockerClient, err := docker.NewClient()
	if err != nil {
		return "", fmt.Errorf("error creating docker client: %v", err)
	}

	dockerClient.PrepareContainer(ctx, develop)

	githubToken, githubUsername, err := services.GetGithubCredentials(ctx)
	if err != nil {
		return "", fmt.Errorf("error getting github credentials: %v", err)
	}

	envVars := map[string]string{}
	envVars["GITHUB_TOKEN"] = githubToken
	envVars["GITHUB_USERNAME"] = githubUsername

	if branchName != "" {
		envVars["BRANCH_NAME"] = branchName
	} else {
		envVars["BRANCH_NAME"] = "main"
	}

	commands := []string{
		"./lib/tasks/scripts/checkout_branch.sh",
		"&&",
		fmt.Sprintf("rake 'github_pipeline:generate_pr_data[%s,%s]'", state, geoid),
	}

	taskResult, err := dockerClient.RunTask(ctx, docker.TaskOptions{
		Develop:      develop,
		Command:      strings.Join(commands, " "),
		EnvVars:      envVars,
		StreamOutput: false,
	})
	if err != nil {
		return "", fmt.Errorf("error running task: %v", err)
	}

	return taskResult.Output, nil
}
