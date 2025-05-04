# frozen_string_literal: true

require_relative "../path_helper"

module Core
  class CityManager
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_people.yml"))
    GOVERNMENT_TYPE_MAYOR_COUNCIL = "mayor_council"

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

    def self.get_search_keywords_as_array(government_type)
      keywords_hash = get_search_keywords(government_type)
      return [] unless keywords_hash

      keywords_hash.map do |name, keywords|
        { name: name, keywords: keywords }
      end
    end
  end
end
