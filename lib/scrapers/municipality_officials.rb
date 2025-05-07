# frozen_string_literal: true

require_relative "wa/municipality_officials/state_level_scraper"
require_relative "or/municipality_officials/state_level_scraper"

module Scrapers
  module MunicipalityOfficials
    def self.fetch_with_state_level(municipality_context)
      city_name = municipality_context[:municipality_entry]["name"]
      state = municipality_context[:state]

      case municipality_context[:state]
      when "wa"
        people = Scrapers::Wa::MunicipalityOfficials::StateLevelScraper.fetch(municipality_context)
      when "or"
        people = Scrapers::Or::MunicipalityOfficials::StateLevelScraper.fetch(municipality_context)
      else
        raise "No state-level scraper found for #{state}"
      end

      raise "No people found for #{city_name}, #{state}" if people.blank?

      {
        "type" => "directory_list",
        "people" => people
      }
    rescue StandardError => e
      puts "Error fetching with state-level scraper for #{city_name}, #{state}: #{e.message}, falling back to search"
      with_search_fallback(municipality_context)
    end

    def self.get_edit_detail(municipality_context)
      state = municipality_context[:state]
      municipality_entry = municipality_context[:municipality_entry]

      case state
      when "wa"
        Scrapers::Wa::MunicipalityOfficials::StateLevelScraper.get_edit_detail(municipality_entry)
      when "or"
        source_url = Scrapers::Or::MunicipalityOfficials::StateLevelScraper.get_source_url(municipality_entry)
        email = "loc@orcities.org"
        { type: "email", data: email, source_url: source_url }
      else
        raise "No state-level scraper found for #{municipality_context[:state]}"
      end
    end

    private_class_method def self.with_search_fallback(municipality_context)
      gemini = Services::GoogleGemini.new
      response = gemini.search_for_people(municipality_context)
      people = response["people"]
      {
        "type" => "directory_list_fallback",
        "people" => people
      }
    end
  end
end
