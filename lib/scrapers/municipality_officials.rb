require_relative "states/wa/local_officials_scrapers/state_level_scraper"
require_relative "states/or/municipality_officials/state_level_scraper"

module Scrapers
  module MunicipalityOfficials
    def self.fetch_with_state_level(municipality_context)
      case municipality_context[:state]
      when "wa"
        Scrapers::States::Wa::LocalOfficialScraper::StateLevelScraper.get_officials(municipality_context)
      when "or"
        Scrapers::Or::MunicipalityOfficials::StateLevelScraper.fetch(municipality_context)
      else
        raise "No state-level scraper found for #{municipality_context[:state]}"
      end
    end
  end
end
