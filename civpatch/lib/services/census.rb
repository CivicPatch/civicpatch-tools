# frozen_string_literal: true

module Services
  class Census
    STATE_TO_STATEFP = {
      "nh" => "33",
      "or" => "41",
      "wa" => "53"
    }.freeze

    YEAR = "2024"

    MAP_TO_URL = {
      "https://www2.census.gov/geo/tiger/TIGER#{YEAR}/PLACE" => "place",
      "https://www2.census.gov/geo/tiger/TIGER#{YEAR}/COUSUB" => "cousub"
    }.freeze

    def self.download_municipalities(state)
      statefp = STATE_TO_STATEFP[state]

      MAP_TO_URL.each do |base_url, map_type|
        url = "#{base_url}/tl_#{YEAR}_#{statefp}_#{map_type}.zip"
        puts "Downloading #{url}..."

        outfile = Tempfile.new(binmode: true)
        begin
          response = HTTParty.get(url, stream_body: true)
          unless response.success? # Check if response code is 2xx
            puts "Error: Failed to download #{url}. HTTP Status: #{response.code} - #{response.message}"
            next # Skip to the next map type
          end
        end

        HTTParty.get(url, stream_body: true) do |fragment|
          next if [301, 302].include?(fragment.code)

          outfile.write(fragment)
        end

        unless response.success? # Check if response code is 2xx
          puts "Error: Failed to download #{url}. HTTP Status: #{response.code} - #{response.message}"
          next # Skip to the next map type
        end

        outfile.rewind

        dest_dir = Core::PathHelper.project_path(File.join("data", state, ".maps", "#{map_type}_#{YEAR}"))

        FileUtils.mkdir_p(dest_dir)

        # Unzip to data_source/<state>/.maps/place_2024
        Zip::File.open(outfile.path) do |zip_file|
          zip_file.each do |entry|
            entry.extract(File.join(dest_dir, entry.name))
          end
        end

        outfile.close
        outfile.unlink
      end
    end

    def self.convert_to_geojson(state, map_directory)
      statefp = STATE_TO_STATEFP[state]
      ## Grab the municipalities from the municipalities.json file
      # municipalities = Core::StateManager.get_municipalities(state)

      # Get the shapefile under the folder
      place_dir = File.join(map_directory, "place_#{YEAR}")
      place_shapefile = File.join(place_dir, "tl_#{YEAR}_#{statefp}_place.shp")
      cousub_dir = File.join(map_directory, "cousub_#{YEAR}")
      cousub_shapefile = File.join(cousub_dir, "tl_#{YEAR}_#{statefp}_cousub.shp")

      # Convert the shapefiles to geojson and output to the data/<state>/municipalities.geojson file
      cousub_geojson = File.join(cousub_dir, "map.geojson")
      ogr2ogr = "ogr2ogr -f GeoJSON -t_srs EPSG:4326 #{cousub_geojson} #{cousub_shapefile}"
      system(ogr2ogr)

      place_geojson = File.join(place_dir, "map.geojson")
      ogr2ogr = "ogr2ogr -f GeoJSON -t_srs EPSG:4326 #{place_geojson} #{place_shapefile}"
      system(ogr2ogr)

      # Combine the two geojson files -- only interested in Name and and GEOID AND only if the GEOID is in the municipalities.json file
      municipalities_geojson = File.join(map_directory, "municipalities.geojson")
      add_cousub = "ogr2ogr -f GeoJSON #{municipalities_geojson} #{cousub_geojson} -nln municipalities"
      system(add_cousub)
      add_place = "ogr2ogr -f GeoJSON -update -append #{municipalities_geojson} #{place_geojson} -nln municipalities"
      system(add_place)

      # Filter out the rows where the GEOID is not in the municipalities.json file
      municipalities_map = File.read(municipalities_geojson)
      map = JSON.parse(municipalities_map)
      features = map["features"]

      municipalities = Core::StateManager.get_municipalities(state)["municipalities"]

      puts "Before filtering: #{features.length} features..."

      keep_features = features.map do |feature|
        has_entry = municipalities.any? { |municipality| municipality["geoid"] == feature["properties"]["GEOID"] }

        next nil unless has_entry

        feature["properties"] = {
          "name" => feature["properties"]["NAME"],
          "geoid" => feature["properties"]["GEOID"]
        }

        feature
      end.compact

      puts "After filtering: #{keep_features.length} features..."

      map["features"] = keep_features

      puts "Found #{map["features"].length} features..."
      File.write(municipalities_geojson, JSON.pretty_generate(map))
    end
  end
end
