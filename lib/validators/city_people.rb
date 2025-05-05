# frozen_string_literal: true

require_relative "./utils"
require_relative "../core/people_resolver"

module Validators
  # List of elected officials for the city (municipality/place)
  class CityPeople
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_people.yml"))

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    def self.validate_sources(municipality_context)
      state = municipality_context[:state]
      gnis = municipality_context[:municipality_entry]["gnis"]
      state_source = municipality_context[:config]["source_directory_list"]["people"]
      people_config = municipality_context[:config]["people"]

      sources_folder_path = PathHelper.get_people_sources_path(state, gnis)
      source_files = Dir.glob(File.join(sources_folder_path, "*.json"))

      sources = [{
        source_name: "state_source",
        people: state_source,
        confidence_score: 0.9
      }]
      source_files.each do |source_file|
        next if source_file.include?("before") # Discard unprocessed results

        source_people = JSON.parse(File.read(source_file))
        source_name = if source_file.include?("openai")
                        "openai"
                      elsif source_file.include?("gemini")
                        "gemini"
                      end

        source = {
          source_name: source_name,
          people: source_people,
          confidence_score: case source_name
                            when "openai"
                              0.7
                            when "gemini"
                              0.7
                            else
                              0.0
                            end
        }
        sources << source
      end

      {
        compare_results: Core::PeopleResolver.compare_people_across_sources(people_config, sources),
        merged_sources: Validators::Utils.merge_people_across_sources(people_config, sources)
      }
    end
  end
end
