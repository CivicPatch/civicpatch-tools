package main

import (
	"fmt"
	"os"
)

var (
	requiredEnvVars = []string{
		"OPENAI_TOKEN",
		"BRAVE_TOKEN",
		"CLOUDFLARE_R2_ENDPOINT", // TODO: Get rid of this
		"CLOUDFLARE_R2_ACCESS_KEY_ID",
		"CLOUDFLARE_R2_SECRET_KEY",
	}

	requiredEnvVarsCI = append(requiredEnvVars,
		"GITHUB_TOKEN",
		"GOOGLE_SEARCH_API_KEY",
		"GOOGLE_SEARCH_ENGINE_ID",
		"GOOGLE_GEMINI_TOKEN",
	)

	requirementsText = map[string]string{
		"GITHUB_TOKEN":            "GITHUB_TOKEN: Set up a PAT or use secrets.GITHUB_TOKEN",
		"OPENAI_TOKEN":            "OPENAI_TOKEN: Set up an OpenAI account and create an API key: https://platform.openai.com/api-keys",
		"BRAVE_TOKEN":             "BRAVE_TOKEN: Set up a Brave Search account and create an API key: https://api-dashboard.search.brave.com/app/keys",
		"GOOGLE_SEARCH_API_KEY":   "GOOGLE_SEARCH_API_KEY: Set up a project with Google Custom Search enabled and create an API key: https://developers.google.com/custom-search/v1/overview",
		"GOOGLE_SEARCH_ENGINE_ID": "GOOGLE_SEARCH_ENGINE_ID: Set up a project with Google Custom Search enabled and get an Engine ID: https://cse.google.com/cse/all",
		"GOOGLE_GEMINI_TOKEN":     "GOOGLE_GEMINI_TOKEN: Set up a project with Google Gemini enabled and create an API key: https://aistudio.google.com/apikey",
	}
)

func checkEnvironmentVariables(envVars []string) {
	for _, envVar := range envVars {
		if os.Getenv(envVar) == "" {
			fmt.Printf("Error: %s is not set\n", envVar)
			fmt.Printf("Please set the environment variable and try again.\n")
			fmt.Printf("For more information, see: %s\n", requirementsText[envVar])
			os.Exit(1)
		}
	}
}
