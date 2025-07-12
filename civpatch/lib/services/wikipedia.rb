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

    def self.fetch_municipalities(title, row_mapping)
      response = fetch_with_wikipedia(title)
      doc = Nokolexbor::HTML(response)
      table = doc.css("table.wikitable.sortable")[0]

      table_rows = table.css("tbody tr")

      parse_municipalities_from_table(table_rows, row_mapping)
    end

    def self.parse_municipalities_from_table(table_rows, row_mapping)
      places = []

      rows = table_rows.drop(row_mapping[:row_start] || 0) # Skip header rows if specified
      rows.each do |city_row|
        columns = city_row.css("td")
        next if columns.empty? # Skip empty rows
        next if columns[row_mapping[:municipality_name]].nil? # Skip rows without municipality name
        municipality_name = format_name(columns[row_mapping[:municipality_name]].text)
        county_names = columns[row_mapping[:county_names]].text
                        .split(",").map do |county|
                          format_name(county)
                        end
        municipality_link = columns[row_mapping[:municipality_name]].css("a")[0].attr("href")

        municipality_page_title = municipality_link.split("/").last

        city_website, fips = fetch_municipality_page(municipality_page_title)

        place = {
          "name" => municipality_name,
          "counties" => county_names,
          "website" => city_website,
          "fips" => fips
        }

        puts "Found municipality: #{municipality_name} in counties: #{county_names.join(", ")} with website: #{city_website} and FIPS: #{fips}"

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

    def self.fetch_municipality_page(wikipedia_title)
      response = fetch_with_wikipedia(wikipedia_title)
      doc = Nokolexbor::HTML(response)

      infobox = doc.css("table.infobox")
      # find tr with th that has a td that contains "website"
      # then find the a tag within that tr that has a href attribute
      website_row = infobox.css("tr").find { |tr| tr.css("th").text.downcase.include?("website") }
      website = website_row.present? ? website_row.css("a").find { |a| a.attr("href") } : nil
      website = website ? Utils::UrlHelper.format_url(website.attr("href")) : ""

      fips_row = infobox.css("tr").find { |tr| tr.css("th").text.downcase.include?("fips") }
      fips = fips_row.present? ? fips_row.css("td").text : ""
      fips = fips.strip.gsub("-", "") # Remove dashes

      if fips.empty?
        puts "Warning: No FIPS code found for #{wikipedia_title}"
      end

      [website, fips]
    end

    # Clean up text

    def self.format_name(name)
      name = name.strip
      # Remove anything that is not a letter, number, dash, apostrophe
      name = name.gsub(/[^a-zA-Z0-9\s'-]/, "")
      name.squeeze(" ").strip # Remove leading/trailing spaces and squeeze multiple spaces
    end
  end
end
