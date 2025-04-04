require_relative "../path_helper"

module Core
  class CityManager
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_directory.yml"))
    GOVERNMENT_TYPES = [MAYOR_COUNCIL = "mayor_council"].freeze

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    def self.get_key_positions(government_type)
      config.dig("government_types", government_type, "key_positions", "role")
    end
  end
end
