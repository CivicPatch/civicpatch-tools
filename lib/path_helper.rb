# frozen_string_literal: true

require "pathname"

module PathHelper
  def self.project_path(relative_path)
    File.expand_path(relative_path, Dir.pwd)
  end

  # Example data/wa/seattle
  def self.city_path_to_city_entry(city_path)
    puts city_path
    city_directory = if File.directory?(city_path)
                       city_path
                     else
                       Pathname(city_path).parent.to_s
                     end

    path_segments = city_directory.split(File::SEPARATOR)
    state = path_segments[-2]
    city = path_segments.last

    city_entries = CityScrape::StateManager.get_state_places(state)
    city_entries["places"].find { |city_entry| city_entry["name"] == city }
  end
end
