require "fuzzy_match"

module CityScrape
  class CityManager
    def self.get_city_directory_file(state, city_entry)
      File.join(get_city_path(state, city_entry), "people.json")
    end

    def self.get_city_directory(state, city_entry)
      city_directory_path = get_city_directory_file(state, city_entry)
      raise "Invalid city directory path: #{city_directory_path}" unless city_directory_path.present?

      JSON.parse(File.read(city_directory_path))
    end
  end
end
