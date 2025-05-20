package docker

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"os/exec"
	"time"

	"civpatch/utils"

	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/filters"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/client"
)

// Client wraps Docker client operations
type Client struct {
	client *client.Client
}

type TaskResult struct {
	ContainerId string
	Output      string
	Logs        io.ReadCloser
	Cancel      context.CancelFunc
}

type TaskOptions struct {
	Develop bool
	// Image        string
	Command string
	EnvVars map[string]string
	// Volumes      map[string]string
	Labels       map[string]string
	Timeout      time.Duration
	StreamOutput bool
}

const (
	ImageName       = "ghcr.io/civicpatch/civpatch"
	LocalImageTag   = "develop"
	RemoteImageTag  = "latest"
	LocalImageName  = ImageName + ":" + LocalImageTag
	RemoteImageName = ImageName + ":" + RemoteImageTag
)

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
func (c *Client) RunTask(ctx context.Context, opts TaskOptions) (*TaskResult, error) {
	var imageName string
	if opts.Develop {
		imageName = LocalImageName
	} else {
		imageName = RemoteImageName
	}

	fmt.Println("Running container with image:", imageName)

	// Convert volume map to binds using projectpath package
	volumes := map[string]string{}

	if opts.Develop {
		volumes = map[string]string{
			"./civpatch/lib": "/app/civpatch/lib",
		}
	}
	binds, err := utils.ToBindMounts(volumes)
	if err != nil {
		return nil, fmt.Errorf("error converting volumes to bind mounts: %v", err)
	}

	env := make([]string, 0, len(opts.EnvVars))
	for k, v := range opts.EnvVars {
		env = append(env, fmt.Sprintf("%s=%s", k, v))
	}

	containerLabels := map[string]string{
		"civicpatch": "true",
	}
	for k, v := range opts.Labels {
		containerLabels[k] = v
	}

	// fullCmd := []string{"/bin/sh", "-c", strings.Join(cmd, " ") + " || true ; tail -f /dev/null"}
	fullCmd := []string{"/bin/sh", "-c", opts.Command}

	resp, err := c.client.ContainerCreate(ctx, &container.Config{
		Image:  imageName,
		Cmd:    fullCmd,
		Env:    env,
		Labels: containerLabels,
	}, &container.HostConfig{
		Binds:      binds,
		AutoRemove: true,
	}, nil, nil, "")

	if err != nil {
		return nil, fmt.Errorf("error creating container: %v", err)
	}

	err = c.client.ContainerStart(ctx, resp.ID, container.StartOptions{})
	if err != nil {
		return nil, fmt.Errorf("error starting container: %v", err)
	}

	// Get container logs
	timeout := 1 * time.Minute
	if opts.Timeout > 0 {
		timeout = opts.Timeout
	}
	logCtx, logCancel := context.WithTimeout(ctx, timeout)
	logs, err := c.client.ContainerLogs(logCtx, resp.ID, container.LogsOptions{
		ShowStdout: true,
		ShowStderr: true,
		Follow:     true,
		Timestamps: false,
		Tail:       "all",
	})
	if err != nil {
		logCancel()
		return nil, fmt.Errorf("error getting container logs: %v", err)
	}

	if !opts.StreamOutput {
		output, err := io.ReadAll(logs)
		if err != nil {
			logCancel()
			return nil, fmt.Errorf("error reading container logs: %v", err)
		}
		logCancel()
		return &TaskResult{
			Output: string(output),
		}, nil
	}

	return &TaskResult{
		ContainerId: resp.ID,
		Logs:        logs,
		Cancel:      logCancel,
	}, nil
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

//func (c *Client) TaskOutput(ctx context.Context, taskOptions TaskOptions) (*ExecResult, error) {
//
//	cmd := []string{"bundle", "exec", "rake", taskOptions.Command}
//
//	exec, err := c.client.ContainerExecCreate(ctx, container.ExecOptions{
//		AttachStdout: true,
//		AttachStderr: true,
//		Cmd:          cmd,
//	})
//	if err != nil {
//		return nil, fmt.Errorf("error creating container exec: %v", err)
//	}
//
//	inspectResp, err := InspectExecResp(ctx, exec.ID)
//	if err != nil {
//		return nil, fmt.Errorf("error inspecting container exec: %v", err)
//	}
//
//	return &ExecResult{
//		Stdout:   inspectResp.Stdout,
//		Stderr:   inspectResp.Stderr,
//		ExitCode: inspectResp.ExitCode,
//	}, nil
//}

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
