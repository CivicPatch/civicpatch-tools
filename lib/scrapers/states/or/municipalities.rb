require "services/wikipedia"

module Scrapers
  module States
    module Or
      class Municipalities
        STATE_SOURCE_URL = "https://www.orcities.org/resources/reference/city-directory"
        STATE_SOURCE_MUNICIPAL_URL = "https://www.orcities.org/resources/reference/city-directory/details"

        def self.fetch
          title = "List_of_cities_in_Oregon"
          municipalities = Services::Wikipedia.fetch_table("wa", title)

          puts municipalities
        end
      end
    end
  end
end