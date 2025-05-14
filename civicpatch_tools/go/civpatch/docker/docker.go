package docker

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/archive"

	"civpatch/utils"
)

// Client wraps Docker client operations
type Client struct {
	client *client.Client
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

// BuildImage builds a Docker image from a local Dockerfile
func (c *Client) BuildImage(ctx context.Context, dockerfilePath string, tag string) error {
	// Convert Dockerfile path to absolute path from project root if it's relative
	if !filepath.IsAbs(dockerfilePath) {
		absPath, err := utils.FromProjectRoot(dockerfilePath)
		if err != nil {
			return fmt.Errorf("error resolving Dockerfile path: %v", err)
		}
		dockerfilePath = absPath
	}

	// Get the directory containing the Dockerfile
	buildContext := filepath.Dir(dockerfilePath)
	dockerfileName := filepath.Base(dockerfilePath)

	// Create a tar archive that respects .dockerignore
	tar, err := archive.TarWithOptions(buildContext, &archive.TarOptions{
		Compression: archive.Uncompressed,
	})
	if err != nil {
		return fmt.Errorf("error creating build context: %v", err)
	}
	defer tar.Close()

	buildResp, err := c.client.ImageBuild(ctx, tar, types.ImageBuildOptions{
		Dockerfile: dockerfileName,
		Tags:       []string{tag},
		Remove:     true,
	})
	if err != nil {
		return fmt.Errorf("error building image: %v", err)
	}
	defer buildResp.Body.Close()

	// Stream the build output
	decoder := json.NewDecoder(buildResp.Body)
	for {
		var buildOutput struct {
			Stream string `json:"stream"`
			Error  string `json:"error"`
		}
		if err := decoder.Decode(&buildOutput); err != nil {
			if err == io.EOF {
				break
			}
			return fmt.Errorf("error decoding build output: %v", err)
		}

		if buildOutput.Error != "" {
			return fmt.Errorf("build error: %s", buildOutput.Error)
		}

		if buildOutput.Stream != "" {
			fmt.Print(buildOutput.Stream)
		}
	}

	// Verify the image exists
	_, err = c.client.ImageInspect(ctx, tag)
	if err != nil {
		return fmt.Errorf("error verifying image: %v", err)
	}

	return nil
}

// ContainerLogs represents the output streams from a container
type ContainerLogs struct {
	Stdout io.ReadCloser
	Stderr io.ReadCloser
}

// RunContainer runs a container with the specified configuration and returns its logs
func (c *Client) RunContainer(ctx context.Context, image string, envVars []string, cmd []string, volumes map[string]string) (string, io.ReadCloser, context.CancelFunc, error) {
	// Convert volume map to container format
	containerVolumes := make(map[string]struct{})
	for path := range volumes {
		containerVolumes[path] = struct{}{}
	}

	// Convert volume map to binds using projectpath package
	binds, err := utils.ToBindMounts(volumes)
	if err != nil {
		return "", nil, nil, fmt.Errorf("error converting volumes to bind mounts: %v", err)
	}

	env := make([]string, len(envVars))
	for i, envVar := range envVars {
		env[i] = fmt.Sprintf("%s=%s", envVar, os.Getenv(envVar))
	}

	fullCmd := []string{"/bin/sh", "-c", strings.Join(cmd, " ") + " && tail -f /dev/null"}

	resp, err := c.client.ContainerCreate(ctx, &container.Config{
		Image:   image,
		Cmd:     fullCmd,
		Env:     env,
		Volumes: containerVolumes,
	}, &container.HostConfig{
		Binds:      binds,
		AutoRemove: true,
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
