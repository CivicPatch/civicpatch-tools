package docker

import (
	"bytes"
	"civpatch/utils"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"time"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/archive"
)

// Client wraps Docker client operations
type Client struct {
	client *client.Client
}

type TaskResult struct {
	ContainerId string
	ExitCode    int
	Output      []byte // If not streaming, capture output here
	Error       error  // If the container itself exited with an error
}

type TaskOptions struct {
	Command string
	EnvVars map[string]string
	Develop bool
	Output  TaskOptionsOutput
}

type TaskOptionsOutput struct {
	StreamOutput bool

	// Mutually exclusive with StreamOutput
	CopyOutputFrom  []string
	CopyOutputToDir string
}

const (
	ImageName       = "ghcr.io/civicpatch/civpatch"
	LocalImageTag   = "develop"
	RemoteImageTag  = "latest"
	LocalImageName  = ImageName + ":" + LocalImageTag
	RemoteImageName = ImageName + ":" + RemoteImageTag
)

func NewClient() (*Client, error) {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, fmt.Errorf("error creating docker client: %v", err)
	}
	return &Client{client: cli}, nil
}

func (c *Client) Close() error {
	return c.client.Close()
}

func (c *Client) RunTask(ctx context.Context, opts TaskOptions) (*TaskResult, error) {
	imageName := toImage(opts.Develop)
	fmt.Println("Running container with image:", imageName)

	env := make([]string, 0, len(opts.EnvVars))
	for k, v := range opts.EnvVars {
		env = append(env, fmt.Sprintf("%s=%s", k, v))
	}

	binds, err := toBindMounts(opts.Develop)
	if err != nil {
		return nil, err
	}

	autoRemove := len(opts.Output.CopyOutputFrom) == 0

	containerID, err := c.createAndStartContainer(ctx, imageName, opts.Command, env, binds, opts.Output.StreamOutput, autoRemove)
	if err != nil {
		return nil, err
	}

	if !autoRemove {
		defer c.cleanupContainer(containerID)
	}

	logsDone, containerDone, errCh, outputBuffer := c.monitorContainer(ctx, containerID, opts.Output.StreamOutput)

	exitCode, finalErr := c.orchestrateResults(containerID, logsDone, containerDone, errCh)

	// Maybe copy files
	if finalErr == nil && len(opts.Output.CopyOutputFrom) > 0 {
		fmt.Printf("Copying output from container %s to host directory %s...\n", containerID, opts.Output.CopyOutputToDir)
		for _, containerPath := range opts.Output.CopyOutputFrom {
			if copyErr := c.copyFromContainer(ctx, containerID, containerPath, opts.Output.CopyOutputToDir); copyErr != nil {
				// We continue with other files, but report the first copy error
				if finalErr == nil {
					finalErr = fmt.Errorf("failed to copy %s from container %s: %w", containerPath, containerID, copyErr)
				}
				fmt.Printf("Warning: %v\n", copyErr) // Log warning for each failed copy
			}
		}
	}

	result := &TaskResult{
		ExitCode: exitCode,
		Error:    finalErr,
	}
	if !opts.Output.StreamOutput {
		result.Output = outputBuffer.Bytes()
	}

	return result, finalErr

}

func toImage(develop bool) string {
	if develop {
		return LocalImageName
	}
	return RemoteImageName
}

func toBindMounts(develop bool) ([]string, error) {
	// Convert volume map to binds using projectpath package
	volumes := map[string]string{}

	if develop {
		volumes = map[string]string{
			"./civpatch/lib": "/app/civpatch/lib",
		}
	}
	binds, err := utils.ToBindMounts(volumes)
	if err != nil {
		return nil, fmt.Errorf("error converting volumes to bind mounts: %v", err)
	}

	return binds, nil
}

func (c *Client) createAndStartContainer(
	ctx context.Context,
	imageName, command string,
	env, binds []string,
	streamOutput, autoRemove bool,
) (string, error) {
	containerLabels := map[string]string{
		"civicpatch": "true",
	}

	// fullCmd := []string{"/bin/sh", "-c", "set -e; " + command + " || true ; tail -f /dev/null"}
	fullCmd := []string{"/bin/sh", "-c", "set -e; " + command}

	resp, err := c.client.ContainerCreate(ctx, &container.Config{
		Image:  imageName,
		Cmd:    fullCmd,
		Env:    env,
		Labels: containerLabels,
		Tty:    streamOutput,
	}, &container.HostConfig{
		Binds:      binds,
		AutoRemove: autoRemove,
	}, nil, nil, "")
	if err != nil {
		return "", fmt.Errorf("error creating container: %w", err)
	}

	containerID := resp.ID
	err = c.client.ContainerStart(ctx, containerID, container.StartOptions{})
	if err != nil {
		return "", fmt.Errorf("error starting container %s: %w", containerID, err)
	}
	fmt.Printf("Container %s started successfully with image: %s\n", containerID, imageName)
	return containerID, nil
}

func (c *Client) monitorContainer(
	ctx context.Context,
	containerID string,
	streamOutput bool,
) (logsDone chan error, containerDone chan container.WaitResponse, errCh chan error, outputBuffer bytes.Buffer) {

	logsDone = make(chan error, 1)
	containerDone = make(chan container.WaitResponse, 1)
	errCh = make(chan error, 1) // For errors from ContainerWait API call

	go func() {
		logOptions := container.LogsOptions{
			ShowStdout: true,
			ShowStderr: true,
			Follow:     true,
			Timestamps: false,
		}
		logsReader, err := c.client.ContainerLogs(ctx, containerID, logOptions)
		if err != nil {
			logsDone <- fmt.Errorf("error getting container logs stream for %s: %w", containerID, err)
			return
		}
		defer logsReader.Close()

		var writer io.Writer
		if streamOutput {
			writer = os.Stdout
		} else {
			writer = &outputBuffer
		}

		_, err = io.Copy(writer, logsReader)
		if err != nil && !errors.Is(err, context.Canceled) { // Ignore context canceled error for logs
			logsDone <- fmt.Errorf("error copying container logs for %s: %w", containerID, err)
			return
		}
		logsDone <- nil
	}()

	go func() {
		statusCh, errStatusCh := c.client.ContainerWait(ctx, containerID, container.WaitConditionNotRunning)
		select {
		case s := <-statusCh:
			containerDone <- s
		case err := <-errStatusCh:
			errCh <- fmt.Errorf("error waiting for container %s: %w", containerID, err)
		case <-ctx.Done():
			errCh <- ctx.Err()
		}
	}()
	return
}

func (c *Client) orchestrateResults(
	containerID string,
	logsDone chan error,
	containerDone chan container.WaitResponse,
	errCh chan error,
) (exitCode int, err error) {
	exitCode = -1 // Default to indicate not set

	select {
	case status := <-containerDone:
		// Container finished, now wait for logs to ensure everything is flushed
		logStreamErr := <-logsDone
		if logStreamErr != nil {
			err = fmt.Errorf("container %s exited, but error occurred during log streaming: %w", containerID, logStreamErr)
		}

		exitCode = int(status.StatusCode)
		if status.Error != nil {
			err = fmt.Errorf("container %s exited with status %d and error message: %s", containerID, status.StatusCode, status.Error.Message)
		} else if exitCode != 0 {
			err = fmt.Errorf("container %s exited with non-zero status: %d", containerID, exitCode)
		}

	case err := <-errCh:
		// Attempt to read logs in case there's any buffered output before stopping
		<-logsDone
		// If context was canceled, ensure the container is stopped
		if errors.Is(err, context.Canceled) {
			fmt.Printf("Context canceled. Stopping container %s...\n", containerID)
			stopCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second) // Give it time to stop
			defer cancel()
			if stopErr := c.client.ContainerStop(stopCtx, containerID, container.StopOptions{}); stopErr != nil {
				fmt.Printf("Warning: failed to stop container %s on context cancellation: %v\n", containerID, stopErr)
			}
		}

	case logStreamErr := <-logsDone:
		// Logs finished before container exited
		if logStreamErr != nil {
			err = fmt.Errorf("error during log streaming for container %s before it exited: %w", containerID, logStreamErr)
		}
		status := <-containerDone
		exitCode = int(status.StatusCode)
		if status.Error != nil {
			err = fmt.Errorf("container %s exited with status %d and error message: %s", containerID, status.StatusCode, status.Error.Message)
		} else if exitCode != 0 {
			err = fmt.Errorf("container %s exited with non-zero status: %d", containerID, exitCode)
		}
	}
	return exitCode, err
}

func (c *Client) cleanupContainer(containerID string) {
	fmt.Printf("Attempting to remove container %s...\n", containerID)
	removeCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second) // Give it a little time
	defer cancel()
	if rmErr := c.client.ContainerRemove(removeCtx, containerID, container.RemoveOptions{}); rmErr != nil {
		fmt.Printf("Warning: failed to remove container %s: %v\n", containerID, rmErr)
	} else {
		fmt.Printf("Successfully removed container %s.\n", containerID)
	}
}

func (c *Client) copyFromContainer(ctx context.Context, containerID, containerPath, hostDirPath string) error {
	// Create the host directory if it doesn't exist
	if err := os.MkdirAll(hostDirPath, 0755); err != nil {
		return fmt.Errorf("failed to create host directory %s: %w", hostDirPath, err)
	}

	// Get file content from container as a tar archive
	reader, _, err := c.client.CopyFromContainer(ctx, containerID, containerPath)
	if err != nil {
		return fmt.Errorf("failed to copy path '%s' from container '%s': %w", containerPath, containerID, err)
	}
	defer reader.Close()

	// Extract the tar archive to the host directory
	if err := archive.CopyTo(reader, archive.CopyInfo{
		Path:  containerPath,
		IsDir: false,
	}, hostDirPath); err != nil {
		return fmt.Errorf("failed to extract tar archive from container path '%s' to '%s': %w", containerPath, hostDirPath, err)
	}

	fmt.Printf("Successfully copied '%s' from container '%s' to '%s'\n", containerPath, containerID, hostDirPath)
	return nil
}

func (c *Client) PrepareContainer(ctx context.Context,
	develop bool,
) error {
	if develop {
		fmt.Println("Building image:", ImageName)
		scriptPath, err := utils.FromProjectRoot("civpatch/build.sh")
		if err != nil {
			return fmt.Errorf("error getting script path: %w", err)
		}

		cmd := exec.Command("bash", scriptPath)
		currentEnv := os.Environ()
		cmd.Env = append(currentEnv,
			"IMAGE_NAME="+ImageName,
			"RELEASE_VERSION="+LocalImageTag,
		)
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr

		fmt.Println("Finished running script")
		if err := cmd.Run(); err != nil {
			return fmt.Errorf("error running script: %w", err)
		}
	} else {
		fmt.Println("Pulling image:", RemoteImageName)
		if err := c.PullImage(ctx, RemoteImageName); err != nil {
			return fmt.Errorf("error pulling image: %w", err)
		}
	}

	return nil
}

func (c *Client) CleanupContainer(ctx context.Context, containerId string) error {
	err := c.client.ContainerStop(ctx, containerId, container.StopOptions{})
	if err != nil {
		return fmt.Errorf("error stopping container: %v", err)
	}
	err = c.client.ContainerRemove(ctx, containerId, container.RemoveOptions{})
	if err != nil {
		return fmt.Errorf("error removing container: %v", err)
	}
	return nil
}

func (c *Client) ListContainers(ctx context.Context) ([]container.Summary, error) {
	containers, err := c.client.ContainerList(ctx, container.ListOptions{
		All: true,
		Filters: filters.NewArgs(
			filters.Arg("label", "civicpatch"),
		),
	})
	if err != nil {
		return nil, fmt.Errorf("error listing containers: %v", err)
	}
	return containers, nil
}

func (c *Client) GetContainerId(ctx context.Context, labels map[string]string) (string, error) {
	filterArgs := filters.NewArgs()
	for k, v := range labels {
		filterArgs.Add("label", fmt.Sprintf("%s=%s", k, v))
	}

	containers, err := c.client.ContainerList(ctx, container.ListOptions{
		Filters: filterArgs,
	})
	if err != nil || len(containers) == 0 {
		return "", fmt.Errorf("error listing containers: %v", err)
	}
	return containers[0].ID, nil
}

func (c *Client) PullImage(ctx context.Context, imageTag string) error {
	fmt.Printf("Attempting to pull %s without explicit credentials (anonymous pull).\n", imageTag)

	pullResp, err_pull := c.client.ImagePull(ctx, imageTag, image.PullOptions{})
	if err_pull != nil {
		return fmt.Errorf("error initiating image pull for %s: %v", imageTag, err_pull)
	}
	defer pullResp.Close()

	// Stream the pull output
	decoder := json.NewDecoder(pullResp)
	for {
		var pullOutput struct {
			Status         string `json:"status"`
			Error          string `json:"error"`
			Progress       string `json:"progress"`
			ProgressDetail struct {
				Current int `json:"current"`
				Total   int `json:"total"`
			} `json:"progressDetail"`
			ID string `json:"id"`
		}
		// Use a new variable for decode error
		err_decode := decoder.Decode(&pullOutput)
		if err_decode != nil {
			if err_decode == io.EOF {
				break // End of stream
			}
			break
		}

		if pullOutput.Error != "" {
			return fmt.Errorf("image pull error for %s: %s", imageTag, pullOutput.Error)
		}

		if pullOutput.Status != "" {
			logMsg := fmt.Sprintf("Status: %s", pullOutput.Status)
			if pullOutput.ID != "" {
				logMsg += fmt.Sprintf(", ID: %s", pullOutput.ID)
			}
			if pullOutput.Progress != "" {
				logMsg += fmt.Sprintf(", Progress: %s", pullOutput.Progress)
			}
			fmt.Println(logMsg)
		}
	}

	// Verify the image exists locally
	// Use a new variable for inspect error
	_, _, err_inspect := c.client.ImageInspectWithRaw(ctx, imageTag)
	if err_inspect != nil {
		return fmt.Errorf("error verifying image %s locally after pull: %v", imageTag, err_inspect)
	}

	fmt.Printf("Successfully pulled image %s\n", imageTag)
	return nil
}
