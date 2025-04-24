require_relative "wa/municipality_officials/state_level_scraper"
require_relative "or/municipality_officials/state_level_scraper"

module Scrapers
  module MunicipalityOfficials
    def self.fetch_with_state_level(municipality_context)
      case municipality_context[:state]
      when "wa"
        Scrapers::Wa::MunicipalityOfficials::StateLevelScraper.get_officials(municipality_context)
      when "or"
        Scrapers::Or::MunicipalityOfficials::StateLevelScraper.fetch(municipality_context)
      else
        raise "No state-level scraper found for #{municipality_context[:state]}"
      end
    end
  end
end
