module Scrapers
  module Us
    module Wa
      class Directory
        def self.get_places
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
            cities << {
              "place" => city["CityName"].downcase.split(" ").join("_"),
              "website" => city["Website"],
              "scraper_misc" => {
                "city_id" => city["CityID"], # specific to only mrsc, subject to change. Used for self.get_representatives
                "population" => city["Population"]
              },
            }
          end

          cities.sort_by { |city| city["scraper_misc"]["population"] }.reverse
        end
      end
    end
  end
end
