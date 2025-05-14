package pipeline

import (
	"civpatch/utils"
	"encoding/json"
	"fmt"
	"io"
	"os"
	"path/filepath"
	"slices"
)

type Municipality struct {
	Name        string   `json:"name"`
	GNIS        string   `json:"gnis"`
	Website     string   `json:"website"`
	MetaSources []string `json:"meta_sources"`
}

func shouldScrape(gnisToIgnore []string, municipality Municipality) bool {
	return !slices.Contains(gnisToIgnore, municipality.GNIS) &&
		len(municipality.GNIS) > 0 &&
		len(municipality.Website) > 0 &&
		(len(municipality.MetaSources) == 0 || len(municipality.MetaSources) == 1)
}

func PickCitiesToScrape(state string, numCities int, gnisToIgnore []string) ([]Municipality, error) {
	projectRoot, err := utils.ProjectRoot()
	if err != nil {
		return nil, err
	}

	citiesFile := filepath.Join(projectRoot, "data", state, "municipalities.json")

	jsonFile, err := os.Open(citiesFile)
	if err != nil {
		fmt.Println("Error opening file:", err)
		return nil, err
	}

	defer jsonFile.Close()

	var municipalities []Municipality

	byteValue, _ := io.ReadAll(jsonFile)

	json.Unmarshal(byteValue, &municipalities)

	fmt.Println(municipalities)

	municipalitiesToScrape := []Municipality{}

	for _, municipality := range municipalities {
		if shouldScrape(gnisToIgnore, municipality) {
			municipalitiesToScrape = append(municipalitiesToScrape, municipality)
		}
		if len(municipalitiesToScrape) >= numCities {
			break
		}
	}

	return municipalitiesToScrape, nil
}
