package services

import (
	"context"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"time"

	"github.com/google/go-github/v72/github"
	"golang.org/x/oauth2"
)

const (
	GITHUB_APP_CLIENT_ID = "Iv23lidh39jVrlDyygqV"
)

// DeviceFlowResponse represents the response from GitHub's device flow endpoint
type DeviceFlowResponse struct {
	DeviceCode      string `json:"device_code"`
	UserCode        string `json:"user_code"`
	VerificationURI string `json:"verification_uri"`
	ExpiresIn       int    `json:"expires_in"`
	Interval        int    `json:"interval"`
}

// DeviceFlow handles GitHub's device flow authentication
type DeviceFlow struct {
	clientID string
	client   *http.Client
	tm       *TokenManager
	config   *oauth2.Config
}

// DeviceFlowState represents a state in the device flow
type DeviceFlowState struct {
	State string
	Desc  string
}

func (e *DeviceFlowState) Error() string {
	return fmt.Sprintf("%s: %s", e.State, e.Desc)
}

// NewGitHubDeviceFlow creates a new device flow handler
func NewGitHubDeviceFlow() (*DeviceFlow, error) {
	tm, err := NewTokenManager()
	if err != nil {
		return nil, fmt.Errorf("failed to create token manager: %w", err)
	}

	// Create OAuth config with minimal required scopes
	config := &oauth2.Config{
		ClientID: GITHUB_APP_CLIENT_ID,
		Endpoint: oauth2.Endpoint{
			TokenURL: "https://github.com/login/oauth/access_token",
		},
		Scopes: []string{"public_repo"}, // Minimal scope needed for PRs
	}

	// Add service to token manager
	tm.AddService("github", config, AuthTypeDeviceFlow)

	return &DeviceFlow{
		clientID: GITHUB_APP_CLIENT_ID,
		client:   &http.Client{},
		tm:       tm,
		config:   config,
	}, nil
}

// GetToken gets a valid token, either from cache or through device flow
func (d *DeviceFlow) GetToken(ctx context.Context) (*oauth2.Token, error) {
	// Try to get token from cache first
	token, err := d.tm.GetToken(ctx, "github")
	if err == nil {
		return token, nil
	}

	// If no valid token in cache, start device flow
	resp, err := d.Start(ctx)
	if err != nil {
		return nil, fmt.Errorf("starting device flow: %w", err)
	}

	fmt.Println("\n=== GitHub Authentication Required ===")
	fmt.Println("To create pull requests, you need to authenticate with GitHub.")
	fmt.Println("\nWhat this means:")
	fmt.Println("- You'll be granting access to create pull requests on public repositories")
	fmt.Println("- The token will be stored locally and you will have to re-authenticate when it expires")
	fmt.Println("\nTo authenticate:")
	fmt.Println("1. Visit:", resp.VerificationURI)
	fmt.Println("2. Enter this code:", resp.UserCode)
	fmt.Println("\nWaiting for you to complete authentication...")
	fmt.Println("(Press Ctrl+C to cancel)")
	fmt.Println("=====================================\n")

	token, err = d.WaitForToken(ctx, resp.DeviceCode, resp.Interval)
	if err != nil {
		return nil, fmt.Errorf("waiting for token: %w", err)
	}

	// Save the token to cache
	if err := d.tm.SaveToken("github", token); err != nil {
		return nil, fmt.Errorf("failed to save token: %w", err)
	}

	return token, nil
}

// Start initiates the device flow and returns the user code and verification URL
func (d *DeviceFlow) Start(ctx context.Context) (*DeviceFlowResponse, error) {
	req, err := http.NewRequestWithContext(ctx, "POST",
		"https://github.com/login/device/code",
		nil)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}

	// Use scopes from config
	q := req.URL.Query()
	q.Add("client_id", d.clientID)
	q.Add("scope", d.config.Scopes[0]) // We only have one scope
	req.URL.RawQuery = q.Encode()

	resp, err := d.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("making request: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("unexpected status: %d, body: %s", resp.StatusCode, string(body))
	}

	return d.parseDeviceFlowResponse(resp.Body)
}

// parseDeviceFlowResponse parses the device flow response from the response body
func (d *DeviceFlow) parseDeviceFlowResponse(body io.Reader) (*DeviceFlowResponse, error) {
	data, err := io.ReadAll(body)
	if err != nil {
		return nil, fmt.Errorf("reading response: %w", err)
	}

	values, err := url.ParseQuery(string(data))
	if err != nil {
		return nil, fmt.Errorf("parsing form data: %w", err)
	}

	expiresIn, _ := strconv.Atoi(values.Get("expires_in"))
	interval, _ := strconv.Atoi(values.Get("interval"))

	return &DeviceFlowResponse{
		DeviceCode:      values.Get("device_code"),
		UserCode:        values.Get("user_code"),
		VerificationURI: values.Get("verification_uri"),
		ExpiresIn:       expiresIn,
		Interval:        interval,
	}, nil
}

// WaitForToken polls GitHub until the user completes the authentication
func (d *DeviceFlow) WaitForToken(ctx context.Context, deviceCode string, interval int) (*oauth2.Token, error) {
	fmt.Printf("Polling every %d seconds for authentication...\n", interval)
	ticker := time.NewTicker(time.Duration(interval) * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return nil, ctx.Err()
		case <-ticker.C:
			fmt.Println("Checking if authentication is complete...")
			token, err := d.pollForToken(ctx, deviceCode)
			if err == nil {
				return token, nil
			}

			// Check if it's a flow state
			if state, ok := err.(*DeviceFlowState); ok {
				switch state.State {
				case "authorization_pending":
					// Normal state, keep polling
					continue
				case "slow_down":
					// Double the interval and continue
					ticker.Reset(time.Duration(interval*2) * time.Second)
					continue
				}
			}
			// For any other error, return it
			return nil, err
		}
	}
}

// pollForToken checks if the user has completed the authentication
func (d *DeviceFlow) pollForToken(ctx context.Context, deviceCode string) (*oauth2.Token, error) {
	req, err := http.NewRequestWithContext(ctx, "POST",
		"https://github.com/login/oauth/access_token",
		nil)
	if err != nil {
		return nil, fmt.Errorf("creating request: %w", err)
	}

	q := req.URL.Query()
	q.Add("client_id", d.clientID)
	q.Add("device_code", deviceCode)
	q.Add("grant_type", "urn:ietf:params:oauth:grant-type:device_code")
	req.URL.RawQuery = q.Encode()

	resp, err := d.client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("making request: %w", err)
	}
	defer resp.Body.Close()

	return d.parseTokenResponse(resp)
}

// parseTokenResponse parses the token response and handles errors
func (d *DeviceFlow) parseTokenResponse(resp *http.Response) (*oauth2.Token, error) {
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("reading response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("unexpected status: %d, body: %s", resp.StatusCode, string(body))
	}

	values, err := url.ParseQuery(string(body))
	if err != nil {
		return nil, fmt.Errorf("parsing form data: %w", err)
	}

	if err := d.checkTokenError(values); err != nil {
		return nil, err
	}

	return d.createToken(values)
}

// checkTokenError checks for error responses in the token response
func (d *DeviceFlow) checkTokenError(values url.Values) error {
	if error := values.Get("error"); error != "" {
		errorDesc := values.Get("error_description")
		switch error {
		case "authorization_pending", "slow_down":
			// These are normal states, not errors
			return &DeviceFlowState{
				State: error,
				Desc:  errorDesc,
			}
		case "expired_token":
			return fmt.Errorf("device code expired: %s", errorDesc)
		case "access_denied":
			return fmt.Errorf("access denied: %s", errorDesc)
		case "unsupported_grant_type":
			return fmt.Errorf("unsupported grant type: %s", errorDesc)
		case "invalid_scope":
			return fmt.Errorf("invalid scope requested: %s", errorDesc)
		default:
			return fmt.Errorf("github oauth error: %s - %s", error, errorDesc)
		}
	}
	return nil
}

// createToken creates an oauth2.Token from the response values
func (d *DeviceFlow) createToken(values url.Values) (*oauth2.Token, error) {
	accessToken := values.Get("access_token")
	if accessToken == "" {
		return nil, fmt.Errorf("no access token in response")
	}

	tokenType := values.Get("token_type")
	if tokenType == "" {
		return nil, fmt.Errorf("no token type in response")
	}

	token := &oauth2.Token{
		AccessToken:  accessToken,
		TokenType:    tokenType,
		RefreshToken: values.Get("refresh_token"),
	}

	if expiresIn := values.Get("expires_in"); expiresIn != "" {
		if seconds, err := strconv.Atoi(expiresIn); err == nil {
			token.Expiry = time.Now().Add(time.Duration(seconds) * time.Second)
		}
	}

	return token, nil
}

// NewClient creates a new GitHub client with the provided token
func (d *DeviceFlow) NewClient(ctx context.Context) (*github.Client, error) {
	token, err := d.GetToken(ctx)
	if err != nil {
		return nil, fmt.Errorf("getting token: %w", err)
	}

	ts := oauth2.StaticTokenSource(token)
	tc := oauth2.NewClient(ctx, ts)
	return github.NewClient(tc), nil
}

func CheckGithubCredentials(ctx context.Context) (githubUsername, githubToken string, err error) {
	if len(os.Getenv("GITHUB_TOKEN")) > 0 && len(os.Getenv("GITHUB_USERNAME")) > 0 {
		return os.Getenv("GITHUB_USERNAME"), os.Getenv("GITHUB_TOKEN"), nil
	}

	// Go through device flow
	deviceFlow, err := NewGitHubDeviceFlow()
	if err != nil {
		return "", "", fmt.Errorf("failed to create device flow: %w", err)
	}

	token, err := deviceFlow.GetToken(ctx)
	if err != nil {
		return "", "", fmt.Errorf("failed to get token: %w", err)
	}

	client, err := deviceFlow.NewClient(ctx)
	if err != nil {
		return "", "", fmt.Errorf("failed to get client: %w", err)
	}

	user, _, err := client.Users.Get(ctx, "")
	if err != nil {
		return "", "", fmt.Errorf("failed to get user: %w", err)
	}

	fmt.Printf("Authenticated as %s\n", *user.Login)

	return *user.Login, token.AccessToken, nil
}
