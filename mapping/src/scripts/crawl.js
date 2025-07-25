const fs = require('fs');
const path = require('path');
const { chromium } = require('patchright');
const yaml = require('js-yaml')

//GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1"
//
//    def self.set_keys
//      @api_key = ENV["GOOGLE_SEARCH_API_KEY"]
//      @search_engine_id = ENV["GOOGLE_SEARCH_ENGINE_ID"]
//    }

//      results = HTTParty.get(
//        "https://api.search.brave.com/res/v1/web/search?q=#{formatted_query}",
//        headers: {
//          "Accept" => "application/json",
//          "Accept-Encoding" => "gzip",
//          "X-Subscription-Token" => ENV["BRAVE_TOKEN"]
//        }

const VARIABLES = {
    "google": {
        "API_URL": "https://www.googleapis.com/customsearch/v1",
        "API_KEY": process.env.GOOGLE_SEARCH_API_KEY,
        "SEARCH_ENGINE_ID": process.env.GOOGLE_SEARCH_ENGINE_ID,
    },
    //"brave": {
    //    "API_URL": "https://api.brave.com/v1/search",
    //    "API_KEY": process.env.BRAVE_TOKEN,
    //}
}

const DIVISION_ATTRIBUTES = {
    "council_district": ["district", "dist"],
    "ward": ["ward"]
}

const HEURISTICS = {
    "divisions_match": {
        name: "MATCHES # DIVISIONS",
        match: (municipality, geojson_data) => {
            feature_count = geojson_data.features.length
            divisions = municipality.divisions
            console.log(`GeoJSON features count: ${feature_count}, Divisions count: ${divisions.length}`);
            return divisions.length === feature_count
        }
    },
    "attributes_match": {
        name: "MATCH ATTRIBUTE NAMES",
        match: (municipality, geojson_data) => {
            // TODO: Normalize the data!
            matched_properties = []
            const division_types_to_look_for = municipality.divisions.reduce((acc, curr) => {
                if (curr.toLowerCase().includes("district")) {
                    return [...acc, "council_district"]
                } else if (curr.toLowerCase().includes("ward")) {
                    return [...acc, "ward"]
                }
            }, [])
            const division_types = [...new Set(division_types_to_look_for)]

            for (const feature of geojson_data.features) {
                const feature_id = feature.id
                const properties = Object.entries(feature.properties);

                for (const division_type of division_types) {
                    attribute_keys_to_look_for = !!municipality.division_attr 
                        ? [municipality.division_attr.toLowerCase()] 
                        : DIVISION_ATTRIBUTES[division_type]
                    console.log("attribute_keys_to_look_for", attribute_keys_to_look_for)

                    candidate = properties.filter(([attr_name, attr_value]) => {
                        return typeof attr_name === 'string' && attribute_keys_to_look_for.some(keyword => attr_name.toLowerCase().includes(keyword));
                    })[0]; // If we have multiple candidates we can grab the most likely based on what is available under municipality.divisions

                    if (!candidate) {
                        return []
                    }

                    const formatted_properties = {
                        feature_id,
                        [division_type]: candidate[1]
                    }

                    matched_properties = [...matched_properties, formatted_properties]
                }
            }

            return matched_properties; // TODO: handle the rest if there are multiple
        }
    }
}

PROJECT_ROOT = path.join(__dirname, '../../..');

const patterns = [
    /rest\/services\/\S+\/FeatureServer\/\d+/,
    /rest\/services\/\S+\/MapServer\/\d+/,
    /rest\/services\/\S+\/MapServer/,
    /rest\/services\/\S+\/MapServer\/identify/,
];

const GEOJSON_QUERY = "?where=1=1&outSR=4326&outFields=*&f=geojson"
// TODO: end of query should be replaced with ?where=1%3D1&outFields=*&f=geojson

const excludedPatterns = [
    /basemaps.arcgis.com/,
    /Elevation\/World_Hillshade/
];

async function search(search_engine = 'google', query) {
    switch (search_engine) {
        case 'google':
            const googleSearchUrl = `${VARIABLES.google.API_URL}?key=${VARIABLES.google.API_KEY}&cx=${VARIABLES.google.SEARCH_ENGINE_ID}&q=${encodeURIComponent(query)}`;
            const response = await fetch(googleSearchUrl);
            if (!response.ok) {
                throw new Error(`Google search failed: ${response.statusText}`);
            }
            return await response.json();
    }
}

// Watch network requests for ArcGIS API calls
async function monitorNetworkRequests(page, duration = 20000) { // duration in milliseconds
    const candidate_urls = [];

    const requestListener = async (request) => {
        const url = request.url();
        if (!excludedPatterns.some(pattern => pattern.test(url))) {
            fs.writeFileSync(path.join(PROJECT_ROOT, "tmp", "output.txt"), `Request URL: ${url}\n`, { flag: 'a' });
        }
        if (patterns.some(pattern => pattern.test(url)) && !excludedPatterns.some(pattern => pattern.test(url))) {
           // Transform request to get just geojson
           const urlObj = new URL(url);

           // If the end of the path is /FeatureServer/<number>, we need to append "query" to the end of the URL
          if (/FeatureServer\/\d+$/.test(urlObj.pathname) || /MapServer\/\d+$/.test(urlObj.pathname)) {
            urlObj.pathname += "/query";
            urlObj.search = GEOJSON_QUERY; 

            let updated_url = urlObj.toString();
            console.log(`Transformed URL: ${updated_url}`); 
            candidate_urls.push(updated_url);
          } else if (/MapServer\/identify/.test(urlObj.pathname)) {
            // If the path is /MapServer/identify, let's grab the layers=visible:0 to form a new request

            const layersParam = urlObj.searchParams.get('layers');
            if (layersParam) {
                // If layers=visible:<digit>, we need to grab the layer number
                layerNumber = layersParam.match(/visible:(\d+)/);
                if (layerNumber && layerNumber[1]) {
                    console.log(`Extracted layer number: ${layerNumber[1]}`);
                    urlObj.pathname = urlObj.pathname.replace(/identify$/, `${layerNumber[1]}/query`);
                    urlObj.search = GEOJSON_QUERY; // Append the query parameters for GeoJSON
                } else {
                    console.error(`Could not extract layer number from layers parameter: ${layersParam}`);
                }
            } else {
                console.error(`No layers parameter found in URL: ${url}`);
            } 

            let updated_url = urlObj.toString();
            console.log(`Transformed URL: ${updated_url}`); 
            candidate_urls.push(updated_url);
          } else if (/MapServer/.test(urlObj.pathname)) {

            // Can't match from the above, so let's get the map server URL (everything until MapServer)
            const mapServerUrl = urlObj.toString().replace(/\/MapServer.*/, '/MapServer');
            const mapServerUrlWithQuery = `${mapServerUrl}?f=json`;
            const data = await fetch(mapServerUrlWithQuery);
            const jsonData = await data.json();
            const layerIds = jsonData.layers.map(layer => layer.id);
            const layerIdsCandidateUrls = layerIds.map(id => `${mapServerUrl}/${id}/query${GEOJSON_QUERY}`);
            candidate_urls.push(...layerIdsCandidateUrls);
          }
        } 


    };

    page.on('request', requestListener);

    // Wait for the specified duration
    await new Promise(resolve => setTimeout(resolve, duration));

    // Stop listening for requests
    page.off('request', requestListener);

    console.log(`Finished monitoring network requests. Detected URLs:`, candidate_urls);
    return candidate_urls;
}

async function searchForMap(url) {
    const browser = await chromium.launch();
    try {
        const page = await browser.newPage();
        console.log("Searching for maps on ", url)
        await page.goto(url);

        // Monitor network requests for 10 seconds
        let candidate_urls = await monitorNetworkRequests(page, 10000);
        candidate_urls = [...new Set(candidate_urls)]; // Remove duplicates
        console.log(`Found ${candidate_urls.length} candidate URLs.`);

        await browser.close();
        return candidate_urls;
    } catch (error) {
        console.error(`Error during search: ${error.message}`);
        return null;
    } finally {
        if (browser) {
            await browser.close();
        }
    }
}

async function processCandidateUrls(candidateUrls, divisions, state, municipalityName) {
    const mismatchedResults = [];

    for (const url of candidateUrls) {
        console.log(`Processing candidate URL: ${url}`);
        let data = null
        try {
            const response = await fetch(url);
            data = await response.json()
        } catch (err) {
            console.error(`No valid geojson data found at ${url}, err: ${err}`)
        }

        // Transform data into geojson format if it is not already
        let geojsonData = null;
        if (data && data.features) {
            geojsonData = data; // Already in GeoJSON format
        } else {
            console.error(`No valid GeoJSON data found at ${url}. Skipping...`);
            continue; // Skip this URL if no valid GeoJSON data is found
        }

        if (geojsonData && geojsonData.features) {
            const featureCount = geojsonData.features.length;
            const divisionsMatch = HEURISTICS["divisions_match"]["match"](municipality, geojsonData)
            console.log('List of attributes:', Object.keys(geojsonData.features[0].properties));

            if (divisionsMatch) {
                console.log(`Feature count matches divisions count. Saving GeoJSON...`);

                attributes_match = HEURISTICS["attributes_match"]["match"](municipality, geojsonData)
                console.log(`Matched attributes:`, attributes_match);

                if (attributes_match.length === 0) {
                    console.error(`No matching attributes found for divisions in ${municipalityName}. Skipping...`);
                    continue; // Skip this URL if no matching attributes are found
                }

                // Update the properties based on the property id
                updated_features = geojsonData.features.map(feature => {
                    updated_properties = attributes_match.find(match => match.feature_id === feature.id)
                    feature.properties = updated_properties 
                    return feature
                })

                geojsonData.features = updated_features

                municipalityFolderName = municipalityName.toLowerCase().replace(/\s+/g, '_');
                const outputPath = path.join(PROJECT_ROOT, 'mapping', 'data_source', state, municipalityFolderName, 'divisions_map.geojson');
                fs.mkdirSync(path.dirname(outputPath), { recursive: true });
                fs.writeFileSync(outputPath, JSON.stringify(geojsonData, null, 2), 'utf8');

                console.log(`GeoJSON saved to ${outputPath}`);
                return geojsonData; // Stop processing and return the result
            } else {
                console.log(`Feature count does not match divisions count.`);
                mismatchedResults.push({
                    candidate_url: url,
                    features_actual: featureCount,
                    features_expected: divisions.length
                });
            }
        }
    }

    console.log(`No matching GeoJSON found for divisions.`);
    return mismatchedResults; // Return mismatched results if no match is found
}

async function crawl(state, geoid) {
    if (VARIABLES.google.API_KEY === undefined || VARIABLES.google.SEARCH_ENGINE_ID === undefined) {
        console.error("Google API key or Search Engine ID is not set. Please set them in your environment variables.");
        return;
    }

    municipalities_file_path = path.join(PROJECT_ROOT, 'mapping', 'data_source', state, 'municipalities.yaml');
    municipalities = fs.existsSync(municipalities_file_path) ? yaml.load(fs.readFileSync(municipalities_file_path)) : [];
    municipality = municipalities.find(m => m.geoid === geoid);

    if (!municipality) {
        console.error(`Municipality with geoid ${geoid} not found in ${municipalities_file_path}`);
        return;
    }

    municipality_name = municipality.name

    if (municipality.map_url) {
        candidate_urls = await searchForMap(municipality.map_url);
    } else { // We need to do a search for it
        search_division = municipality.divisions.toLowerCase().includes("district") ? "district" : "ward";
        const searchQuery = `${municipality_name}, ${state} council member ${search_division} map`;
        const results = await search('google', searchQuery);
        console.log("results", results);
    }

    processCandidateUrls(candidate_urls, municipality.divisions, state, municipality_name)
}

// Example usage

// Parse command-line arguments
const args = process.argv.slice(2);
if (!args[0] || !args[1]) {
    console.log("No arguments found, defaulting to state: wa and geoid: 5367000 (Spokane)")
}
const state = args[0] || 'wa'; // Default to 'wa' if no state is provided
const geoid = args[1] || '5367000'; // Default to '5367000' if no geoid is provided

crawl(state, geoid);