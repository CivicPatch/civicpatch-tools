# frozen_string_literal: true

require "pathname"
require "utils/folder_helper"
require_relative "state_manager"

module Core
  class PathHelper
    def self.project_path(relative_path)
      File.expand_path(relative_path, Dir.pwd)
    end

    def self.format_name(name)
      name.downcase.gsub(" ", "_")
    end

    def self.get_municipality_config_path(state, geoid)
      municipality_path = PathHelper.get_data_source_city_path(state, geoid)
      PathHelper.project_path(File.join(municipality_path, "config.yml"))
    end

    def self.get_unique_city_name(state, geoid)
      city_entry = Core::StateManager.get_city_entry_by_geoid(state, geoid)
      state_places = Core::StateManager.get_municipalities(state)

      path_name = city_entry["name"]

      # Some cities within the same state have the same name
      if state_places["municipalities"].count { |place| place["name"] == city_entry["name"] } > 1
        path_name = "#{city_entry["name"]}_#{city_entry["geoid"]}"
      end

      format_name(path_name)
    end

    def self.get_data_source_city_path(state, geoid)
      unique_city_name = get_unique_city_name(state, geoid)
      PathHelper.project_path(File.join("data_source", state, unique_city_name))
    end

    def self.get_data_city_path(state, geoid)
      unique_city_name = get_unique_city_name(state, geoid)
      PathHelper.project_path(File.join("data", state, unique_city_name))
    end

    def self.get_city_cache_path(state, geoid)
      data_source_city_path = get_data_source_city_path(state, geoid)
      PathHelper.project_path(File.join(data_source_city_path, "cache"))
    end

    def self.get_people_sources_path(state, geoid)
      city_path = get_data_source_city_path(state, geoid)
      File.join(city_path, "people")
    end

    # source, gemini, scrape
    def self.get_people_candidates_file_path(state, geoid, directory_type)
      people_folder_path = get_people_sources_path(state, geoid)
      FileUtils.mkdir_p(people_folder_path)
      File.join(people_folder_path, "people_#{directory_type}.json")
    end

    def self.get_data_source_images_path(state, geoid)
      city_path = get_data_source_city_path(state, geoid)
      File.join(city_path, "images")
    end

    def self.get_data_images_path(state, geoid)
      city_path = get_data_city_path(state, geoid)
      File.join(city_path, "images")
    end
  end
end
