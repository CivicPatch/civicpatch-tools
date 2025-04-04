require_relative "states/wa/places"

module Scrapers
  class Places
    def self.get_places_scraper(state)
      case state
      when "wa"
        Scrapers::States::Wa::Places
      else
        raise NotImplementedError
      end
    end

    def self.fetch_places(state)
      scraper = get_places_scraper(state)
      scraper.fetch_places
    end
  end
end
