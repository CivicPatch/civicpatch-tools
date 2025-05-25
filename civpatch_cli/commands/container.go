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

func RunTask(ctx context.Context,
	branchName string,
	command string,
	develop bool,
) (string, error) {
	if branchName == "" {
		return "", fmt.Errorf("must use with -branch-name")
	}

	if command == "" {
		return "", fmt.Errorf("must use with -command")
	}

	fmt.Printf("Running task: %s\n", command)

	dockerClient, err := docker.NewClient()
	if err != nil {
		return "", fmt.Errorf("error creating docker client: %v", err)
	}

	dockerClient.PrepareContainer(ctx, develop)

	githubUsername, githubToken, err := services.GetGithubCredentials(ctx)
	if err != nil {
		return "", fmt.Errorf("error getting github credentials: %v", err)
	}

	envVars := map[string]string{}
	envVars["GITHUB_USERNAME"] = githubUsername
	envVars["GITHUB_TOKEN"] = githubToken
	envVars["GH_TOKEN"] = githubToken

	if branchName != "" {
		envVars["BRANCH_NAME"] = branchName
	} else {
		envVars["BRANCH_NAME"] = "main"
	}

	commands := []string{
		"./lib/tasks/scripts/checkout_branch.sh",
		"&&",
		command,
	}

	taskResult, err := dockerClient.RunTask(ctx, docker.TaskOptions{
		Develop: develop,
		Command: strings.Join(commands, " "),
		EnvVars: envVars,
		Output: docker.TaskOptionsOutput{
			StreamOutput: false,
		},
	})
	if err != nil {
		return "", fmt.Errorf("error running task: %v", err)
	}

	return string(taskResult.Output), nil
}
