# frozen_string_literal: true

require_relative "path_helper"

module Core
  class ConfigManager
    DEFAULT_CONFIG = {
      "sources" => [],
      "people" => {} # Maintain a list keyed by people names
    }.freeze

    def self.config_path(state, geoid)
      municipal_path = Core::PathHelper.get_data_source_city_path(state, geoid)
      File.join(municipal_path, "config.yml")
    end

    def self.get_config(state, geoid)
      config_file_path = config_path(state, geoid)
      saved_config = YAML.load_file(config_file_path) if File.exist?(config_file_path)

      return DEFAULT_CONFIG.merge(saved_config) if saved_config.present?

      DEFAULT_CONFIG.dup
    end

    def self.update_config(state, geoid, config, **updates)
      updated_config = config.dup
      updated_config = updated_config.merge(updates.stringify_keys)
      config_file_path = config_path(state, geoid)
      File.write(config_file_path, updated_config.to_yaml)

      config
    end

    def self.finalize_config(state, geoid, config)
      people_config = config["people"]

      people_config.each do |name, person_config|
        # remove entries that doen't have any other_names set
        unless person_config["other_names"].present? && person_config["other_names"].count.positive?
          people_config.delete(name)
        end
      end
      config["people"] = people_config

      Core::ConfigManager.update_config(state, geoid, config)
    end
  end
end
