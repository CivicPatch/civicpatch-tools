# frozen_string_literal: true

require_relative "../../common"

module Scrapers
  module Us
    module Mi 
      class Directory
        def self.fetch_places
          title = "List_of_municipalities_in_Michigan"

          response = Scrapers::Common.fetch_with_wikipedia(title)
          nokogiri_doc = Nokogiri::HTML(response)
          table = nokogiri_doc.css("table.wikitable")[0]
          table_rows = table.css("tr")[2..]

          cities = Scrapers::Common.parse_cities_from_wikipedia_table("mi", table_rows)
          cities.sort_by { |city| city["population"] }.reverse
        end
      end
    end
  end
end
