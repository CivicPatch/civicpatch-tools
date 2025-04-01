# frozen_string_literal: true

require_relative "../../../tasks/city_scrape/state_manager"
require_relative "../../../scrapers/standard"

module Scrapers
  module Us
    module Wa
      class Directory
        def self.fetch_places
          title = "List_of_municipalities_in_Washington"
          cities = Scrapers::Common.fetch_places_from_wikipedia("wa", title)

          cities.sort_by { |city| city["population"] }.reverse
        end
      end
    end
  end
end
