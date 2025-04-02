# frozen_string_literal: true

require_relative "../../services/wikipedia"
require_relative "../../services/wa_source"

module Scrapers
  module Wa
    class Places
      def self.fetch_places
        title = "List_of_municipalities_in_Washington"
        cities = Services::Wikipedia.fetch_places_from_wikipedia("wa", title)

        sorted_cities = cities.sort_by { |city| city["population"] }.reverse

        source_cities = Services::WaSource.get_places_list
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
    end
  end
end
