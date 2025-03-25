# frozen_string_literal: true

require_relative "../../common"

module Scrapers
  module Us
    module Mi 
      class Directory
        def self.fetch_places
          title = "List_of_municipalities_in_Michigan"
          cities = fetch_cities(title)

          cities.sort_by { |city| city["scraper_misc"]["population"] }.reverse
        end

        def self.fetch_cities(title)
          places = []

          response = self.fetch_with_wikipedia(title)

          nokogiri_doc = Nokogiri::HTML(response)
          table = nokogiri_doc.css("table.wikitable")[0]

            # for every tr that has a tr with a wikilink
            city_rows = table.css("tr").select do |tr|
              tr.css("a").any? { |a|
                a.attr("rel") == "mw:WikiLink"
              }
            end

            # ignore header rows
            city_rows[1..].each do |city_row|
              columns = city_row.css("td")
              city_name = Scrapers::Common.format_name(columns[0].text)
              city_type = Scrapers::Common.format_name(columns[1].text)
              county_name = Scrapers::Common.format_name(columns[2].text)
              city_link = columns[0].css("a")[0].attr("href")
              puts "Fetching city: #{city_name}"

              city_page_title = city_link.split("/").last
              city_population = columns[3].text.gsub(/[^\d]/, "").to_i

              #city_website = fetch_city_website(city_page_title)

              places << {
                "place" => city_name,
                "county" => county_name,
                #"website" => city_website,
                "type" => city_type,
                "scraper_misc" => {
                  "population" => city_population,
                  "wikipedia_page_title" => city_page_title
                }
              }
            end
          places
        end

        def self.fetch_city_website(wikipedia_title)
          response = fetch_with_wikipedia(wikipedia_title)
          nokogiri_doc = Nokogiri::HTML(response)

          infobox = nokogiri_doc.css("table.infobox")
          # find tr with th that has a td that contains "website"
          # then find the a tag within that tr that has a href attribute
          website_row = infobox.css("tr").find { |tr| tr.css("th").text.downcase.include?("website") }
          website = website_row.present? ? website_row.css("a").find { |a| a.attr("href") } : nil
          website ? Scrapers::Common.format_url(website.attr("href")) : ""
        end

        def self.fetch_with_wikipedia(title)
          url = "https://en.wikipedia.org/api/rest_v1/page/html/#{title}"
          response = HTTParty.get(url)

          raise "Error: #{response.code}" unless response.success?

          response.parsed_response
        end

        def self.calculate_meta(places)
          num_places = places.count.to_f
          {
            "has_website_percentage" => places.count { |place| place["website"].present? } / num_places * 100,
            "city_percentage" => places.count { |place| place["type"] == "city" } / num_places * 100,
            "charter_township_percentage" => places.count { |place| place["type"] == "charter_township" } / num_places * 100
          }
        end
      end
    end
  end
end
