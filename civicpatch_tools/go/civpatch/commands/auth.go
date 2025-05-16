package commands

import (
	"civpatch/services"
	"fmt"
)

// AuthClear clears the cached GitHub token.
func AuthClear() error {
	tm, err := services.NewTokenManager()
	if err != nil {
		return fmt.Errorf("failed to create token manager: %w", err)
	}
	if err := tm.ClearToken("github"); err != nil {
		return fmt.Errorf("failed to clear GitHub token: %w", err)
	}
	fmt.Println("GitHub token cache cleared.")
	return nil
}
