package docker

import (
	"context"
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"strings"
	"time"

	"civpatch/utils"

	"github.com/docker/docker/api/types"
	"github.com/docker/docker/api/types/container"
	"github.com/docker/docker/api/types/image"
	"github.com/docker/docker/api/types/registry"
	"github.com/docker/docker/client"
	"github.com/docker/docker/pkg/archive"
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
func (c *Client) RunContainer(ctx context.Context, image string, envVars []string, args map[string]string, cmd []string, volumes map[string]string) (string, io.ReadCloser, context.CancelFunc, error) {
	// Convert volume map to binds using projectpath package
	binds, err := utils.ToBindMounts(volumes)
	if err != nil {
		return "", nil, nil, fmt.Errorf("error converting volumes to bind mounts: %v", err)
	}

	env := make([]string, len(envVars))
	for i, envVar := range envVars {
		if args[envVar] != "" {
			env[i] = fmt.Sprintf("%s=%s", envVar, args[envVar])
		} else {
			env[i] = fmt.Sprintf("%s=%s", envVar, os.Getenv(envVar))
		}
	}

	fullCmd := []string{"/bin/sh", "-c", strings.Join(cmd, " ") + " || true ; tail -f /dev/null"}

	resp, err := c.client.ContainerCreate(ctx, &container.Config{
		Image: image,
		Cmd:   fullCmd,
		Env:   env,
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

// PushImage pushes a Docker image to a remote registry.
// username and password must be provided.
func (c *Client) PushImage(ctx context.Context, imageTag string, username string, password string) error {
	if username == "" || password == "" {
		return fmt.Errorf("username and password must be provided to push image %s", imageTag)
	}

	authConfig := registry.AuthConfig{
		Username: username,
		Password: password,
	}
	encodedJSON, err_marshal := json.Marshal(authConfig) // Use new variable for this specific error
	if err_marshal != nil {
		return fmt.Errorf("error marshalling auth config for %s: %v", imageTag, err_marshal)
	}
	authStr := base64.URLEncoding.EncodeToString(encodedJSON)

	pushResp, err_push := c.client.ImagePush(ctx, imageTag, image.PushOptions{ // Use new variable for this specific error
		RegistryAuth: authStr,
	})
	if err_push != nil {
		return fmt.Errorf("error pushing image %s: %v", imageTag, err_push)
	}
	defer pushResp.Close()

	// Stream the push output
	decoder := json.NewDecoder(pushResp)
	for {
		var pushOutput struct {
			Status         string `json:"status"`
			Error          string `json:"error"`
			Progress       string `json:"progress"`
			ProgressDetail struct {
				Current int `json:"current"`
				Total   int `json:"total"`
			} `json:"progressDetail"`
		}
		// Use a new variable for decode error
		err_decode := decoder.Decode(&pushOutput)
		if err_decode != nil {
			if err_decode == io.EOF {
				break // End of stream
			}
			break
		}

		if pushOutput.Error != "" {
			if strings.Contains(strings.ToLower(pushOutput.Status), "unauthorized") || strings.Contains(strings.ToLower(pushOutput.Status), "denied") {
				return fmt.Errorf("image push authorization error for %s: %s. Check credentials and permissions", imageTag, pushOutput.Status)
			}
			return fmt.Errorf("image push error for %s: %s", imageTag, pushOutput.Error)
		}

		if pushOutput.Status != "" {
			if strings.Contains(strings.ToLower(pushOutput.Status), "unauthorized") || strings.Contains(strings.ToLower(pushOutput.Status), "denied") {
				return fmt.Errorf("image push authorization error for %s: %s. Check credentials and permissions", imageTag, pushOutput.Status)
			}
			if pushOutput.Progress != "" {
				fmt.Printf("Status: %s, Progress: %s\n", pushOutput.Status, pushOutput.Progress)
			} else {
				fmt.Printf("Status: %s\n", pushOutput.Status)
			}
		}
	}

	fmt.Printf("Successfully pushed image %s\n", imageTag)
	return nil
}
