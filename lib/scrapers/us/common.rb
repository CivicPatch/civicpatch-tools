require_relative "wa/places"

module Scrapers
  class City
    def self.validate_place_directory(state, gnis)
      case state
      when "wa"
        Scrapers::Us::Wa::Place.validate_place_directory(gnis)
      else
        raise NotImplementedError
      end
    end
  end
end
