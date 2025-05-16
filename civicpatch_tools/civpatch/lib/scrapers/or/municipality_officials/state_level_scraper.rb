# frozen_string_literal: true

require "utils/name_helper"
module Scrapers
  module Or
    module MunicipalityOfficials
      class StateLevelScraper
        MUNICIPALITY_DIRECTORY_URL = "https://www.orcities.org/resources/reference/city-directory"

        def self.get_source_url(municipality_entry)
          municipality_name = municipality_entry["name"]
          municipality_name = if municipality_name.start_with?("Mount ")
                                municipality_name.gsub("Mount ",
                                                       "Mt ")
                              else
                                municipality_name
                              end
          key = municipality_name.downcase.gsub(" ", "-")
          "#{MUNICIPALITY_DIRECTORY_URL}/details/#{key}"
        end

        def self.fetch(municipality_context)
          municipality_entry = municipality_context[:municipality_entry]
          source_url = get_source_url(municipality_entry)
          # Fetch HTML, interacting to select "All" entries
          response = Browser.fetch_page_content(source_url) do |browser|
            # Create a Select object and choose the "All" option by its value ("-1")
            page.select_option("select#dtCityContacts_length", value: "-1")

            # Wait briefly for the table to potentially update after changing pagination
            # A more robust wait might look for staleness or specific element changes
            # Example: wait for the first row of the table body to be present again
            sleep(2)
            browser.query_selector("#dtCityContacts tbody tr")
          end
          # Ensure response is not nil before parsing
          parse_html(response[:page_html])
        rescue StandardError => e
          puts "Could not fetch directory list: #{e}"
          []
        end

        def self.parse_html(html)
          doc = Nokogiri::HTML(html)
          officials = []

          # Find the table containing contacts
          table = doc.at_xpath("//table[@id='dtCityContacts']")

          # Check if the table exists
          return officials unless table

          # Iterate over the rows in the table body
          table.xpath(".//tbody/tr").each do |row|
            cells = row.xpath(".//td")
            # Ensure there are enough cells before extracting
            next unless cells.length >= 4

            officials << {
              "name" => Utils::NameHelper.format_name(cells[0].text.strip),
              "positions" => [cells[1].text.strip],
              "email" => cells[2].text.strip,
              "phone_number" => cells[3].text.strip
            }
          end

          officials
        end
      end
    end
  end
end
