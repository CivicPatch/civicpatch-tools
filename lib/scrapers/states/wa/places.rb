# frozen_string_literal: true

require_relative "../../../services/wikipedia"

module Scrapers
  module States
    module Wa
      class Places
        STATE_SOURCE_URL = "https://mrsc.org/research-tools/washington-city-and-town-profiles"
        STATE_SOURCE_CITY_PAGE_URL = "https://mrsc.org/research-tools/washington-city-and-town-profiles/city-officials"

        def self.fetch
          title = "List_of_municipalities_in_Washington"
          cities = Services::Wikipedia.fetch_places_from_wikipedia("wa", title)

          sorted_cities = cities.sort_by { |city| city["population"] }.reverse
          source_cities = get_places_list
          with_government_types(source_cities, sorted_cities)
        end

        def self.with_government_types(source_cities, cities)
          cities.each do |city|
            # Assumption: no cities in washington
            # have the same name
            city_with_info = source_cities.find do |source_city|
              source_city["name"].downcase == city["name"].gsub("_", " ").downcase
            end

            next unless city_with_info.present?

            city["government_type"] = city_with_info["government_type"]
          end
        end

        def self.get_places_list
          response = HTTParty.get(STATE_SOURCE_URL)
          document = Nokogiri::HTML(response.body)

          data = document.css("#tableCityProfiles").attr("data-data")
          cities = JSON.parse(data)
          cities.map do |city|
            {
              "name" => city["CityName"],
              "city_id" => city["CityID"],
              "website" => city["Website"],
              "government_type" => city["FormofGov"]
            }
          end
        end
      end
    end
  end
end
