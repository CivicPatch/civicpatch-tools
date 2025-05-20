package docker

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"strings"
	"time"

	"civpatch/utils"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/api/types/registry"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/stdcopy"
)

// Client wraps Docker client operations
type Client struct {
	client *client.Client
}

type ExecResult struct {
	Stdout   string
	Stderr   string
	ExitCode int
}

// NewClient creates a new Docker client
func NewClient() (*Client, error) {
	cli, err := client.NewClientWithOpts(client.FromEnv, client.WithAPIVersionNegotiation())
	if err != nil {
		return nil, fmt.Errorf("error creating docker client: %v", err)
	}
	return &Client{client: cli}, nil
}

// Close closes the Docker client
func (c *Client) Close() error {
	return c.client.Close()
}

// ContainerLogs represents the output streams from a container
type ContainerLogs struct {
	Stdout io.ReadCloser
	Stderr io.ReadCloser
}

// RunContainer runs a container with the specified configuration and returns its logs
func (c *Client) RunContainer(ctx context.Context,
	image string, envVars map[string]string,
	cmd []string,
	volumes map[string]string,
	labels map[string]string) (string, io.ReadCloser, context.CancelFunc, error) {
	// Convert volume map to binds using projectpath package
	binds, err := utils.ToBindMounts(volumes)
	if err != nil {
		return "", nil, nil, fmt.Errorf("error converting volumes to bind mounts: %v", err)
	}

	env := make([]string, 0, len(envVars))
	for k, v := range envVars {
		env = append(env, fmt.Sprintf("%s=%s", k, v))
	}

	containerLabels := map[string]string{
		"civicpatch": "true",
	}
	for k, v := range labels {
		containerLabels[k] = v
	}

	fullCmd := []string{"/bin/sh", "-c", strings.Join(cmd, " ") + " || true ; tail -f /dev/null"}
	// fullCmd := []string{"/bin/sh", "-c", strings.Join(cmd, " ")}

	resp, err := c.client.ContainerCreate(ctx, &container.Config{
		Image:  image,
		Cmd:    fullCmd,
		Env:    env,
		Labels: containerLabels,
	}, &container.HostConfig{
		Binds: binds,
		// AutoRemove: true,
	}, nil, nil, "")

	if err != nil {
		return "", nil, nil, fmt.Errorf("error creating container: %v", err)
	}

	err = c.client.ContainerStart(ctx, resp.ID, container.StartOptions{})
	if err != nil {
		return "", nil, nil, fmt.Errorf("error starting container: %v", err)
	}

	// Get container logs
	logCtx, logCancel := context.WithTimeout(ctx, 10*time.Minute)
	logs, err := c.client.ContainerLogs(logCtx, resp.ID, container.LogsOptions{
		ShowStdout: true,
		ShowStderr: true,
		Follow:     true,
		Timestamps: false,
		Tail:       "all",
		Since:      "0",
		Until:      "",
	})
	if err != nil {
		logCancel()
		return resp.ID, nil, nil, fmt.Errorf("error getting container logs: %v", err)
	}

	return resp.ID, logs, logCancel, nil
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

func (c *Client) ExecCommand(ctx context.Context, containerId string, command string) (*ExecResult, error) {
	cmd := []string{"bundle", "exec", "rake", command}

	exec, err := c.client.ContainerExecCreate(ctx, containerId, container.ExecOptions{
		AttachStdout: true,
		AttachStderr: true,
		Cmd:          cmd,
	})
	if err != nil {
		return nil, fmt.Errorf("error creating container exec: %v", err)
	}

	inspectResp, err := InspectExecResp(ctx, exec.ID)
	if err != nil {
		return nil, fmt.Errorf("error inspecting container exec: %v", err)
	}

	return &ExecResult{
		Stdout:   inspectResp.Stdout,
		Stderr:   inspectResp.Stderr,
		ExitCode: inspectResp.ExitCode,
	}, nil
}

func InspectExecResp(ctx context.Context, id string) (ExecResult, error) {
	var execResult ExecResult
	docker, err := client.NewClientWithOpts()
	if err != nil {
		return execResult, err
	}
	defer docker.Close()

	resp, err := docker.ContainerExecAttach(ctx, id, container.ExecAttachOptions{})
	if err != nil {
		return execResult, err
	}
	defer resp.Close()

	// read the output
	var outBuf, errBuf bytes.Buffer
	outputDone := make(chan error)

	go func() {
		// StdCopy demultiplexes the stream into two buffers
		_, err = stdcopy.StdCopy(&outBuf, &errBuf, resp.Reader)
		outputDone <- err
	}()

	select {
	case err := <-outputDone:
		if err != nil {
			return execResult, err
		}
		break

	case <-ctx.Done():
		return execResult, ctx.Err()
	}

	stdout, err := io.ReadAll(&outBuf)
	if err != nil {
		return execResult, err
	}
	stderr, err := io.ReadAll(&errBuf)
	if err != nil {
		return execResult, err
	}

	res, err := docker.ContainerExecInspect(ctx, id)
	if err != nil {
		return execResult, err
	}

	execResult.ExitCode = res.ExitCode
	execResult.Stdout = string(stdout)
	execResult.Stderr = string(stderr)
	return execResult, nil
}

func (c *Client) PullImage(ctx context.Context, imageTag string, username string, password string) error {
	var authStr string

	if username != "" && password != "" {
		authConfig := registry.AuthConfig{
			Username: username,
			Password: password,
		}
		encodedJSON, err_marshal := json.Marshal(authConfig)
		if err_marshal != nil {
			return fmt.Errorf("error marshalling auth config for %s: %v", imageTag, err_marshal)
		}
		authStr = base64.URLEncoding.EncodeToString(encodedJSON)
		fmt.Printf("Attempting to pull %s with provided credentials (username: %s).\n", imageTag, username)
	} else {
		fmt.Printf("Attempting to pull %s without explicit credentials (anonymous pull).\n", imageTag)
	}

	pullResp, err_pull := c.client.ImagePull(ctx, imageTag, image.PullOptions{ // Use new variable for this specific error
		RegistryAuth: authStr, // Empty string if no auth provided
	})
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
