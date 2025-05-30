# frozen_string_literal: true

require "utils/url_helper"

module Services
  class Wikipedia
    URL = "https://en.wikipedia.org/api/rest_v1/page/html"

    # test = {
    #  row_start: 1,

    #  city_name: 0,
    #  county: 1,
    #  population: 2
    # }

    def self.fetch_municipalities(state, title, table_data_config)
      response = fetch_with_wikipedia(title)
      nokogiri_doc = Nokogiri::HTML(response)
      table = nokogiri_doc.css("table.wikitable.sortable")[0]

      table_rows = table.css("tr")

      parse_municipalities_from_table(state, table_rows, table_data_config)
    end

    def self.parse_cities_from_table(state, table_rows, _row_data_config)
      places = []
      table_rows.css("tr").each do |city_row|
        puts city_row
        columns = city_row.css("td, th")
        city_name = format_name(columns[0].text)
        city_type = columns[1].text
        county_names = without_superscripts(columns[2])
                       .text.split(",").map do |county|
          format_name(county)
        end
        city_link = columns[0].css("a")[0].attr("href")

        city_page_title = city_link.split("/").last
        city_population = columns[3].text.gsub(/[^\d]/, "").to_i

        puts "Fetching city page for #{city_name}"

        city_website, fips, gnis = fetch_city_page(city_page_title)

        place = {
          "ocd_ids" => generate_ocd_ids(state, county_names, city_name),
          "name" => city_name,
          "counties" => county_names,
          "website" => city_website,
          "fips" => fips,
          "gnis" => gnis,
          "type" => city_type,
          "population" => city_population
        }

        places << place
      end

      places
    end

    def self.fetch_with_wikipedia(title)
      url = "#{URL}/#{title}"
      response = HTTParty.get(url)

      raise "Error: #{response.code}" unless response.success?

      response.parsed_response
    end

    def self.fetch_city_page(wikipedia_title)
      response = fetch_with_wikipedia(wikipedia_title)
      nokogiri_doc = Nokogiri::HTML(response)

      infobox = nokogiri_doc.css("table.infobox")
      # find tr with th that has a td that contains "website"
      # then find the a tag within that tr that has a href attribute
      website_row = infobox.css("tr").find { |tr| tr.css("th").text.downcase.include?("website") }
      website = website_row.present? ? website_row.css("a").find { |a| a.attr("href") } : nil
      website = website ? Utils::UrlHelper.format_url(website.attr("href")) : ""

      fips_row = infobox.css("tr").find { |tr| tr.css("th").text.downcase.include?("fips") }
      fips = fips_row.present? ? without_superscripts(fips_row.css("td")).text : ""

      geoid_row = infobox.css("tr").find { |tr| tr.css("th").text.downcase.include?("geoid") }
      geoid = geoid_row.present? ? without_superscripts(geoid_row.css("td")).text : ""

      [website, fips, geoid]
    end

    # Clean up text

    def self.format_municipality_name(name)
      name = name.gsub("[c]", "")
      name = name.gsub("†", "")
      name = name.gsub("‡", "")
      # get rid of trailing spaces
      name = name.gsub(/\s+$/, "")
      # convert to key-friendly format
      name = name.gsub(" ", "_").downcase

      # get weird of wikipedia symbols
      name.gsub(" ", "_")
    end

    def self.without_superscripts(nokogiri_doc)
      nokogiri_doc.css("sup").each(&:remove) # Remove <sup> elements entirely
      nokogiri_doc # Return the modified document
    end

    def self.generate_ocd_ids(state, county_names, city_name)
      ocd_ids = [
        "ocd-division/country:us/state:#{state}/place:#{city_name}"
      ]

      county_names.each do |county_name|
        ocd_ids << "ocd-division/country:us/state:#{state}/county:#{county_name}/place:#{city_name}"
      end

      ocd_ids
    end
  end
end
