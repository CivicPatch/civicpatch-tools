require "nokogiri"
require "open-uri"
require "yaml"

module Scrapers
  class Wa
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
            "city_id" => city["CityID"] # specific to only mrsc, subject to change. Used for self.get_representatives
          }
        }
      end

      cities
    end

    # def self.get_representatives(place)
    #  url = "https://mrsc.org/research-tools/washington-city-and-town-profiles/city-officials?cityID=#{place["scraper_misc"]["city_id"]}"

    #  html = HTTParty.get(url).body
    #  doc = Nokogiri::HTML(html)

    #  # this is very hacky, but it works for now
    #  table = doc.at_css("table.table-bordered")

    #  representatives = []

    #  table.css("tr").each do |row|
    #    cells = row.css("td")
    #    if cells.length == 2
    #      title = cells[0].text.strip
    #      name = cells[1].text.strip

    #      if title.include?("Mayor") || title.include?("Councilmember")
    #        if title.include?("Mayor")
    #          title = "mayor"
    #        else
    #          title = "council_member"
    #        end

    #        representatives << {
    #          "title" => title,
    #          "name" => name
    #        }
    #      end
    #    end
    #  end

    #  representatives
    # end
  end
end
