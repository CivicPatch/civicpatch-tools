const fs = require('fs');
const path = require('path');
const yaml = require('js-yaml');

PROJECT_ROOT = path.join(__dirname, '../../..');
CIVPATCH_ROOT = path.join(PROJECT_ROOT, 'civpatch');
GEOCODING_ROOT = path.join(PROJECT_ROOT, 'geocoding');

// Function to read JSON file, extract specific fields, convert to YAML, and merge data
function sync(state) {
    const state_data_path = path.join(CIVPATCH_ROOT, "data", state);
    const input_path = path.join(CIVPATCH_ROOT, "data_source", state, "municipalities.json");
    const output_path = path.join(GEOCODING_ROOT, "data_source", state, "municipalities.yaml");

    // Check if JSON file exists
    if (!fs.existsSync(input_path)) {
        console.error(`JSON file not found: ${input_path}`);
        return;
    }

    // Read JSON file
    const jsonData = JSON.parse(fs.readFileSync(input_path, 'utf8'));
    const municipalities = jsonData["municipalities"] || [];

    console.log(`Processing ${municipalities.length} municipalities from ${input_path}`);

    // Check if YAML file exists
    let yamlData = [];
    if (fs.existsSync(output_path)) {
        yamlData = yaml.load(fs.readFileSync(output_path, 'utf8')) || [];
    }

    // Extract specific fields and merge data
    
    // Convert yamlData (a list) into a dictionary for easier merging
    let mergedData = {};
    mergedData = yamlData.reduce((acc, item) => {
        const key = item.geoid; // Use "geoid" as the unique identifier
        acc[key] = item;
        return acc;
    }, {});

    municipalities.forEach((item) => {
        municipality_name = item.name.split(" ").join("_").toLowerCase();
        candidate_people_paths = [
            path.join(state_data_path, municipality_name, "people.yml"),
            path.join(state_data_path, [municipality_name, item.geoid].join("_"), "people.yaml"), // When mulitple cities share the same name within a state, this is how they are stored
        ]

        people_path = null

        if (fs.existsSync(candidate_people_paths[0])) {
            people_path = candidate_people_paths[0];
        } else if (fs.existsSync(candidate_people_paths[1])) {
            people_path = candidate_people_paths[1];
        } else {
            console.warn(`No people file found for ${item.name} (${item.geoid})`);
            people_path = null; // Set to null if no file found
        }

        // Set up a list to collect unique divisions
        let divisions = [];

        if (people_path) {
            // For each person, collect the list of unique divisions
            // We are only interested in "district" or "ward" divisions
            const peopleData = yaml.load(fs.readFileSync(people_path, 'utf8')) || [];
            peopleData.forEach((person) => {
                if (person.divisions) {
                    person.divisions.forEach((division) => {
                        if (division.toLowerCase().includes("district") || division.toLowerCase().includes("ward")) {
                            divisions.push(division);
                        }
                    });
                }
            })
        }

        divisions = [...new Set(divisions)]; // Remove duplicates

        const key = item.geoid; // Use "geoid" as the unique identifier
        if (!mergedData[key]) {
            mergedData[key] = {};
        }

        mergedData[key].name = item.name;
        mergedData[key].geoid = item.geoid;
        mergedData[key].ocdid = item.ocdid;
        mergedData[key].ocdids = item.ocdids;
        mergedData[key].website= item.website; // Add the path to the people file
        mergedData[key].divisions = divisions.sort(); // Add the unique divisions
        mergedData[key].population = item.population || 0; // Add population if available
    });

    mergedDataList = Object.values(mergedData).sort((a, b) => {
        // Sort by population, then by name
        if (a.population !== b.population) {
            return b.population - a.population; // Sort by population descending
        }
        return a.name.localeCompare(b.name); // Sort by name ascending
    });

    // Write merged data to YAML file
    fs.writeFileSync(output_path, yaml.dump(mergedDataList), 'utf8');
    console.log(`YAML file updated: ${output_path}`);
}

// Example usage
const state = 'wa'; // Replace with the desired state
sync(state);