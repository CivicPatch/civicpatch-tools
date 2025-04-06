require_relative "../path_helper"

module Core
  class CityManager
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_people.yml"))
    GOVERNMENT_TYPE_MAYOR_COUNCIL = "mayor_council".freeze

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    def self.get_positions(government_type)
      config.dig("government_types", government_type, "positions")
    end

    def self.get_position_roles(government_type)
      config.dig("government_types", government_type, "positions")
            .map { |position| position["role"] }
    end

    def self.get_position_divisions(government_type)
      config.dig("government_types", government_type, "positions")
            .flat_map { |position| position["implied_by"] || [] }
    end

    def self.get_position_examples(government_type)
      config.dig("government_types", government_type, "position_examples")
    end

    def self.get_search_keywords(government_type)
      config.dig("government_types", government_type, "search_keywords")
    end
  end
end
