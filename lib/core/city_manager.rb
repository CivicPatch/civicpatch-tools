# frozen_string_literal: true

require_relative "../path_helper"

module Core
  class CityManager
    CONFIG_PATH = PathHelper.project_path(File.join("config", "government_types.yml"))
    GOVERNMENT_TYPE_MAYOR_COUNCIL = "mayor_council"

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    def self.get_config(government_type)
      config.dig("government_types", government_type)
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
