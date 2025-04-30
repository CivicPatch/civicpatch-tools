require "path_helper"

module Core
  class ConfigManager
    DEFAULT_CONFIG = {
      "scrape_sources" => [],
      "scrape_exit_config" => {
        "people_count" => 5,
        "key_position" => "mayor"
      }, # Just defaults, need to overwrite
      "people" => {}, # Maintain a list keyed by people names
      "divisions_map" => nil # A map of districts/wards, if available
    }.freeze

    def self.config_path(state, gnis)
      municipal_path = PathHelper.get_data_source_city_path(state, gnis)
      File.join(municipal_path, "config.yml")
    end

    def self.get_config(state, gnis)
      config_file_path = config_path(state, gnis)
      saved_config = YAML.load_file(config_file_path) if File.exist?(config_file_path)

      if saved_config.present?
        saved_config.merge(DEFAULT_CONFIG)
      else
        DEFAULT_CONFIG.dup
      end
    end

    def self.update_config(state, gnis, config)
      config_file_path = config_path(state, gnis)
      File.write(config_file_path, config.to_yaml)

      config
    end
  end
end
