package utils

import (
	"fmt"
	"os"
	"strings"
)

var (
	RequiredScrapeEnvVars = []string{
		"OPENAI_TOKEN",
		"BRAVE_TOKEN",
		"GOOGLE_SEARCH_API_KEY",
		"GOOGLE_SEARCH_ENGINE_ID",
		"GOOGLE_GEMINI_TOKEN",
		//"CLOUDFLARE_R2_ENDPOINT", // TODO: Get rid of this
		//"CLOUDFLARE_R2_ACCESS_KEY_ID",
		//"CLOUDFLARE_R2_SECRET_KEY",
	}

	RequiredEnvVarsCI = []string{
		"GITHUB_TOKEN",
		"GITHUB_USERNAME",
	}

	RequiredEnvVarsSendCosts = []string{
		"GOOGLE_SHEETS_SPREADSHEET_ID",
		"GOOGLE_SHEETS_CLIENT_ID",
		"GOOGLE_SHEETS_CLIENT_SECRET",
		"GOOGLE_SHEETS_REFRESH_TOKEN",
	}

	requirementsText = map[string]string{
		"GITHUB_USERNAME":         "GITHUB_USERNAME: Set up a GitHub account and create a username (for pipelines, use github.actor)",
		"GITHUB_TOKEN":            "GITHUB_TOKEN: Set up a PAT or use secrets.GITHUB_TOKEN (for pipelines, use secrets.GITHUB_TOKEN)",
		"OPENAI_TOKEN":            "OPENAI_TOKEN: Set up an OpenAI account and create an API key: https://platform.openai.com/api-keys",
		"BRAVE_TOKEN":             "BRAVE_TOKEN: Set up a Brave Search account and create an API key: https://api-dashboard.search.brave.com/app/keys",
		"GOOGLE_SEARCH_API_KEY":   "GOOGLE_SEARCH_API_KEY: Set up a project with Google Custom Search enabled and create an API key: https://developers.google.com/custom-search/v1/overview",
		"GOOGLE_SEARCH_ENGINE_ID": "GOOGLE_SEARCH_ENGINE_ID: Set up a project with Google Custom Search enabled and get an Engine ID: https://cse.google.com/cse/all",
		"GOOGLE_GEMINI_TOKEN":     "GOOGLE_GEMINI_TOKEN: Set up a project with Google Gemini enabled and create an API key: https://aistudio.google.com/apikey",
	}
)

func CheckEnvironmentVariables(envVars []string) error {
	errorStringLines := []string{}
	for _, envVar := range envVars {
		if os.Getenv(envVar) == "" {
			errorStringLines = append(errorStringLines, requirementsText[envVar])
		}
	}

	if len(errorStringLines) > 0 {
		return fmt.Errorf("Missing environment variables:\n%s", strings.Join(errorStringLines, "\n"))
	}
	return nil
}
