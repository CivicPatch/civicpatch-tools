require_relative "states/wa/places"
require_relative "states/or/municipalities"

module Scrapers
  class Places
    def self.get_municipalities_scraper(state)
      case state
      when "wa"
        Scrapers::States::Wa::Places
      when "or"
        Scrapers::States::Or::Municipalities
      else
        raise NotImplementedError
      end
    end

    def self.fetch(state)
      scraper = get_municipalities_scraper(state)
      scraper.fetch
    end
  end
end
