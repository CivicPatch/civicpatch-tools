# frozen_string_literal: true

module Scrapers
  module Us
    module Wa
      class Directory
        def self.fetch_places
          url = "https://mrsc.org/research-tools/washington-city-and-town-profiles"

          # Open the URL and parse the HTML
          html = HTTParty.get(url).body
          doc = Nokogiri::HTML(html)

          cities = []

          # Iterate over each city/town link
          table = doc.at_css("#tableCityProfiles")
          raw_cities = table["data-data"]
          data = JSON.parse(raw_cities)
          data.each do |city|
            county_name = Scrapers::Common.format_name(city["County"])
            city_name = Scrapers::Common.format_name(city["CityName"])
            city_type = Scrapers::Common.format_name(city["Class"]) # First, Second, code city, town, or unclassified
            cities << {
              "ocd_id" => "ocd-division/country:us/state:wa/county:#{county_name}/place:#{city_name}",
              "name" => city_name,
              "county" => county_name,
              "website" => city["Website"],
              "type" => city_type,
              "scraper_misc" => {
                "city_id" => city["CityID"], # specific to only mrsc, subject to change. Used for self.get_representatives
                "population" => city["Population"]
              }
            }
          end

          cities.sort_by { |city| city["scraper_misc"]["population"] }.reverse
        end
      end
    end
  end
end
