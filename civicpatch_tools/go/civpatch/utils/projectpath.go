package utils

import (
	"fmt"
	"path/filepath"
	"runtime"
	"strings"
)

// ProjectRoot returns the absolute path to the project root (4 levels up from this package)
func ProjectRoot() (string, error) {
	// Get the directory where this package is located
	_, currentFile, _, ok := runtime.Caller(0)
	if !ok {
		return "", fmt.Errorf("failed to get current file path")
	}

	// Go up 4 levels from the package location
	packageDir := filepath.Dir(currentFile)
	projectRoot := filepath.Join(packageDir, "..", "..", "..", "..")

	return filepath.Abs(projectRoot)
}

// FromProjectRoot converts a path relative to the project root to an absolute path
// Example: FromProjectRoot("Dockerfile") -> "/absolute/path/to/civpatch-tools/Dockerfile"
func FromProjectRoot(relativePath string) (string, error) {
	root, err := ProjectRoot()
	if err != nil {
		return "", err
	}
	return filepath.Abs(filepath.Join(root, relativePath))
}

// ToContainerPath converts a host path to container path format
// On Windows: C:\path\to\dir -> /c/path/to/dir
// On Unix: /path/to/dir -> /path/to/dir
func ToContainerPath(hostPath string) string {
	// Convert to forward slashes
	containerPath := filepath.ToSlash(hostPath)

	// Handle Windows paths
	if runtime.GOOS == "windows" {
		if filepath.VolumeName(hostPath) != "" {
			// If it's an absolute path with drive letter
			drive := strings.ToLower(hostPath[0:1])
			containerPath = "/" + drive + containerPath[2:]
		}
	}

	return containerPath
}

// ToBindMount converts a host:container path pair to bind mount format
// If hostPath is relative, it's assumed to be relative to the project root
func ToBindMount(hostPath, containerPath string) (string, error) {
	// If hostPath is relative, convert it to absolute from project root
	if !filepath.IsAbs(hostPath) {
		absPath, err := FromProjectRoot(hostPath)
		if err != nil {
			return "", err
		}
		hostPath = absPath
	}
	return ToContainerPath(hostPath) + ":" + containerPath + ":ro", nil
}

// ToBindMounts converts a map of host:container paths to bind mount format
// If host paths are relative, they're assumed to be relative to the project root
func ToBindMounts(volumes map[string]string) ([]string, error) {
	var binds []string
	for host, container := range volumes {
		bind, err := ToBindMount(host, container)
		if err != nil {
			return nil, err
		}
		binds = append(binds, bind)
	}
	return binds, nil
}

func ToTmpfsMount(hostPath, containerPath string) (string, error) {
	return ToContainerPath(hostPath) + ":" + containerPath + ":rw,exec", nil
}

func ToTmpfsMounts(volumes map[string]string) (map[string]string, error) {
	binds := make(map[string]string)
	for host, container := range volumes {
		bind, err := ToTmpfsMount(host, container)
		if err != nil {
			return nil, err
		}
		binds[host] = bind
	}
	return binds, nil
}
