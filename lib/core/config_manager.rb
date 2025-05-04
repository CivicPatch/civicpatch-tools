require "path_helper"

module Core
  class ConfigManager
    DEFAULT_CONFIG = {
      "scrape_sources" => [],
      "source_directory_list" => {
        "type" => "directory_list_default",
        "people" => [nil, nil, nil, nil, nil], # Absolute default is 5 people
        "key_position" => "mayor"
      }, # Just defaults, need to overwrite
      "people" => {} # Maintain a list keyed by people names
    }.freeze

    def self.config_path(state, gnis)
      municipal_path = PathHelper.get_data_source_city_path(state, gnis)
      File.join(municipal_path, "config.yml")
    end

    def self.get_config(state, gnis)
      config_file_path = config_path(state, gnis)
      saved_config = YAML.load_file(config_file_path) if File.exist?(config_file_path)

      if saved_config.present?
        DEFAULT_CONFIG.merge(saved_config)
      else
        DEFAULT_CONFIG.dup
      end
    end

    def self.update_config(state, gnis, config)
      config_file_path = config_path(state, gnis)
      File.write(config_file_path, config.to_yaml)

      config
    end

    def self.cleanup(state, gnis, config)
      people_config = config["people"]

      people_config.each do |name, person_config|
        # remove entries that doen't have any other_names set
        unless person_config["other_names"].present? && person_config["other_names"].count.positive?
          people_config.delete(name)
        end
      end
      config["people"] = people_config

      Core::ConfigManager.update_config(state, gnis, config)
    end
  end
end
