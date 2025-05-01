require "utils/name_helper"
module Scrapers::Or::MunicipalityOfficials
  class StateLevelScraper
    MUNICIPALITY_DIRECTORY_URL = "https://www.orcities.org/resources/reference/city-directory".freeze

    def self.get_source_url(municipality_context)
      key = municipality_context[:municipality_entry]["name"].downcase.gsub(" ", "-")
      "#{MUNICIPALITY_DIRECTORY_URL}/details/#{key}"
    end

    def self.fetch(municipality_context)
      url = get_source_url(municipality_context)
      # Fetch HTML, interacting to select "All" entries
      response = Browser.fetch_html(url) do |browser, wait|
        # Find the select element for pagination length
        select_element = wait.until do
          browser.find_element(css: "select[name='dtCityContacts_length']")
        end

        # Create a Select object and choose the "All" option by its value ("-1")
        select_list = Selenium::WebDriver::Support::Select.new(select_element)
        select_list.select_by(:value, "-1")

        # Wait briefly for the table to potentially update after changing pagination
        # A more robust wait might look for staleness or specific element changes
        # Example: wait for the first row of the table body to be present again
        wait.until { browser.find_element(css: "#dtCityContacts tbody tr") }
      rescue Selenium::WebDriver::Error::TimeoutError, Selenium::WebDriver::Error::NoSuchElementError => e
        puts "Could not find or interact with pagination elements for #{url}: #{e.message}"
        # Decide whether to proceed with potentially incomplete data or raise an error
      end
      # Ensure response is not nil before parsing
      response ? parse_html(response) : []
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
