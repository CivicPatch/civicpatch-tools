# frozen_string_literal: true

require_relative "./utils"

module Validators
  # List of elected officials for the city (municipality/place)
  class CityPeople
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_people.yml"))

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    def self.validate_sources(state, gnis)
      sources_folder_path = PathHelper.get_city_people_sources_path(state, gnis)
      source_files = Dir.glob(File.join(sources_folder_path, "*.yml"))

      sources = []
      source_files.each do |source_file|
        next if source_file.include?("before") # Discard unprocessed results

        source_people = YAML.load_file(source_file)
        source_name = if source_file.include?("state_source")
                        "state_source"
                      elsif source_file.include?("scrape")
                        "scrape"
                      elsif source_file.include?("gemini")
                        "gemini"
                      end

        source = {
          source_name: source_name,
          people: source_people,
          confidence_score: case source_name
                            when "state_source"
                              0.9
                            when "scrape"
                              0.7
                            when "gemini"
                              0.6 # TODO: you hallucinate a lot!
                            else
                              0.0
                            end
        }
        sources << source
      end

      compare_results = Validators::Utils.compare_people_across_sources(sources)
      contested_names = compare_results[:contested_names]

      {
        compare_results: compare_results,
        merged_sources: Validators::Utils.merge_people_across_sources(sources, contested_names)
      }
    end
  end
end
