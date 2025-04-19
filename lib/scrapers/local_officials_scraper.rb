require_relative "states/wa/local_officials_scrapers/state_level_scraper"

module Scrapers
  module LocalOfficialScraper
    def self.fetch_with_state_source(state, city_entry)
      case state
      when "wa"
        Scrapers::States::Wa::LocalOfficialScraper::StateLevelScraper.get_officials(city_entry)
      else
        raise "No state-level scraper found for #{state}"
      end
    end
  end
end
