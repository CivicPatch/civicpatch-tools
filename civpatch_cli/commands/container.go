package commands

import (
	"civpatch/docker"
	"context"
	"fmt"
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

func RunRakeTask(ctx context.Context, state string, gnis string, command string) (string, error) {
	if state == "" || gnis == "" || command == "" {
		return "", fmt.Errorf("error: state, gnis, and command are required")
	}

	dockerClient, err := docker.NewClient()
	if err != nil {
		return "", fmt.Errorf("error creating docker client: %v", err)
	}

	containerId, err := dockerClient.GetContainerId(ctx, map[string]string{
		"state": state,
		"gnis":  gnis,
	})
	if err != nil {
		return "", fmt.Errorf("error getting container id: %v", err)
	}

	cmd, err := dockerClient.ExecCommand(ctx, containerId, command)
	if err != nil {
		return "", fmt.Errorf("error executing command: %v", err)
	}

	if cmd.ExitCode != 0 {
		return "", fmt.Errorf("error executing with exit code: %v with stderr: %v", cmd.ExitCode, cmd.Stderr)
	}

	fmt.Println("Command output:", cmd.Stdout)

	return cmd.Stdout, nil
}
