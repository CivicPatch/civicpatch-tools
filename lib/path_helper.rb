# frozen_string_literal: true

require "pathname"

module PathHelper
  def self.project_path(relative_path)
    File.expand_path(relative_path, Dir.pwd)
  end

  def self.get_state_path(state)
    PathHelper.project_path("data/#{state}")
  end

  def self.get_city_path(state, gnis)
    state_path = get_state_path(state)

    city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    state_places = CityScrape::StateManager.get_state_places(state)

    path_name = city_entry["name"]

    # Some cities within the same state have the same name
    if state_places["places"].count { |place| place["name"] == city_entry["name"] } > 1
      path_name = "#{city_entry["name"]}_#{city_entry["gnis"]}"
    end

    File.join(state_path, path_name)
  end

  def self.get_city_people_sources_path(state, gnis)
    city_path = get_city_path(state, gnis)
    File.join(city_path, "people")
  end

  def self.get_city_people_candidates_file_path(state, gnis, directory_type) # source, gemini, scrape
    people_folder_path = get_city_people_sources_path(state, gnis)
    FileUtils.mkdir_p(people_folder_path)
    File.join(people_folder_path, "people_#{directory_type}.yml")
  end
end
