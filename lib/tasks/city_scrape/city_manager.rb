require "fuzzy_match"

module CityScrape
  class CityManager
    # sort by position - mayor first, then council_president, then council_member
    # if there is no position, then sort by position_misc alphabetically, then name
    # position and position_misc are optional, so we need to handle nil values

    def self.get_city_path(state, city_entry)
      state_path = CityScrape::StateManager.get_state_path(state)
      city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, city_entry["gnis"])
      state_places = CityScrape::StateManager.get_state_places(state)

      path_name = city_entry["name"]

      # Some cities within the same state have the same name
      if state_places["places"].count { |place| place["name"] == city_entry["name"] } > 1
        path_name = "#{city_entry["name"]}_#{city_entry["gnis"]}"
      end

      File.join(state_path, path_name)
    end

    def self.get_city_directory_file(state, city_entry)
      File.join(get_city_path(state, city_entry), "directory.yml")
    end

    def self.get_city_directory(state, city_entry)
      city_directory_path = get_city_directory_file(state, city_entry)
      raise "Invalid city directory path: #{city_directory_path}" unless city_directory_path.present?

      YAML.load(File.read(city_directory_path))
    end
  end
end
