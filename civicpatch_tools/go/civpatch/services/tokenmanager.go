// tokenmanager/tokenmanager.go
package services

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"time"

	"golang.org/x/oauth2"
)

// AuthType defines the type of OAuth flow
type AuthType string

const (
	AuthTypeDeviceFlow AuthType = "device_flow"
)

// TokenManager handles token caching and refresh for multiple services
type TokenManager struct {
	services map[string]*ServiceConfig
	cacheDir string
}

type cachedToken struct {
	Token     *oauth2.Token `json:"token"`
	ExpiresAt time.Time     `json:"expires_at"`
}

// ServiceConfig represents the OAuth2 configuration for a service
type ServiceConfig struct {
	ServiceName string
	Config      *oauth2.Config
	AuthType    AuthType
	// For device flow
	DeviceCode   string
	UserCode     string
	PollInterval int
}

// NewTokenManager creates a new token manager
func NewTokenManager() (*TokenManager, error) {
	cacheDir, err := os.UserCacheDir()
	if err != nil {
		return nil, fmt.Errorf("failed to get user cache dir: %w", err)
	}

	appCacheDir := filepath.Join(cacheDir, "civpatch")
	if err := os.MkdirAll(appCacheDir, 0700); err != nil {
		return nil, fmt.Errorf("failed to create cache directory: %w", err)
	}

	return &TokenManager{
		services: make(map[string]*ServiceConfig),
		cacheDir: appCacheDir,
	}, nil
}

// AddService adds a new service configuration
func (tm *TokenManager) AddService(serviceName string, config *oauth2.Config, authType AuthType) error {
	if config == nil {
		return fmt.Errorf("config cannot be nil")
	}
	if serviceName == "" {
		return fmt.Errorf("service name cannot be empty")
	}

	tm.services[serviceName] = &ServiceConfig{
		ServiceName: serviceName,
		Config:      config,
		AuthType:    authType,
	}
	return nil
}

// GetToken retrieves a token for a service, refreshing if necessary
func (tm *TokenManager) GetToken(ctx context.Context, serviceName string) (*oauth2.Token, error) {
	if _, ok := tm.services[serviceName]; !ok {
		return nil, fmt.Errorf("service %q not found in token manager", serviceName)
	}

	// Try to get token from cache
	cachePath := tm.getCachePath(serviceName)
	if data, err := os.ReadFile(cachePath); err == nil {
		var cached cachedToken
		if err := json.Unmarshal(data, &cached); err == nil {
			if time.Now().Before(cached.ExpiresAt) && cached.Token.Valid() {
				return cached.Token, nil
			}
		}
	}

	return nil, fmt.Errorf("no valid token found")
}

// SaveToken saves a token to the cache
func (tm *TokenManager) SaveToken(serviceName string, token *oauth2.Token) error {
	if _, ok := tm.services[serviceName]; !ok {
		return fmt.Errorf("service %q not found in token manager", serviceName)
	}

	cached := cachedToken{
		Token:     token,
		ExpiresAt: time.Now().Add(7 * 24 * time.Hour),
	}

	data, err := json.Marshal(cached)
	if err != nil {
		return fmt.Errorf("failed to marshal token: %w", err)
	}

	cachePath := tm.getCachePath(serviceName)
	if err := os.WriteFile(cachePath, data, 0600); err != nil {
		return fmt.Errorf("failed to cache token: %w", err)
	}

	return nil
}

// ClearToken removes a cached token for a service
func (tm *TokenManager) ClearToken(serviceName string) error {
	return os.Remove(tm.getCachePath(serviceName))
}

// getCachePath returns the path to the token cache file for a service
func (tm *TokenManager) getCachePath(serviceName string) string {
	return filepath.Join(tm.cacheDir, fmt.Sprintf("%s_token.json", serviceName))
}
