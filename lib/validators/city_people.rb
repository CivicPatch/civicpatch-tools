# frozen_string_literal: true

require_relative "./utils"

module Validators
  # List of elected officials for the city (municipality/place)
  class CityPeople
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_directory.yml"))
    VALIDATORS = [SOURCE = "source", GEMINI = "gemini"].freeze

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    def self.validate_sources(state, gnis)
      sources_folder_path = PathHelper.get_city_people_sources_path(state, gnis)
      source_files = Dir.glob(File.join(sources_folder_path, "*.yml"))

      sources = []
      confidence_scores = []
      source_files.each do |source_file|
        source_directory = YAML.load_file(source_file)
        sources << source_directory
        confidence_scores << if source_file.include?("source")
                               0.9
                             elsif source_file.include?("scrape")
                               0.8
                             elsif source_file.include?("gemini")
                               0.8
                             else
                               0.0
                             end
      end

      puts "sources: #{sources.count}"
      Validators::Utils.compare_people_across_sources(sources, confidence_scores)
    end
  end
end
