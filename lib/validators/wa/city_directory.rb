# frozen_string_literal: true

# Washington-specific validator

module Validators
  module Wa
    class CityDirectory
      STATE = "wa"
      STATE_SOURCE_URL = "https://mrsc.org/research-tools/washington-city-and-town-profiles"
      STATE_SOURCE_CITY_PAGE_URL = "https://mrsc.org/research-tools/washington-city-and-town-profiles/city-officials"

      def self.get_valid_city_directory(gnis)
        city_entry = CityScrape::StateManager.get_city_entry_by_gnis(STATE, gnis)

        city_website = city_entry["website"]
        fetch_source_city_officials(city_website)
      end

      def self.fetch_source_city_officials(website)
        city_id = scrape_state_source_for_city_id(website)

        raise "No city found with website: #{website}" if city_id.nil?

        scrape_state_source_city_page_for_directory(city_id)
      end

      def self.scrape_state_source_for_city_id(website)
        response = HTTParty.get(STATE_SOURCE_URL)
        document = Nokogiri::HTML(response.body)

        data = document.css("#tableCityProfiles").attr("data-data")
        cities = JSON.parse(data)
        found_city = cities.find do |city|
          city["Website"].present? && city["Website"].downcase.include?(without_prefix(website.downcase))
        end

        found_city["CityID"]
      end

      def self.scrape_state_source_city_page_for_directory(city_id)
        source_url = "#{STATE_SOURCE_CITY_PAGE_URL}?cityID=#{city_id}"
        response = HTTParty.get(source_url)
        document = Nokogiri::HTML(response.body)
        data = document.css("table")[1].attr("data-data")
        city_officials_data = JSON.parse(data)
        city_officials = city_officials_data.map { |person| extract_person_info(person) }
        city_officials.reject do |city_official|
          Scrapers::CityDirectory::KEY_POSITIONS.none? do |key_position|
            city_official["positions"].include?(key_position)
          end
        end
      end

      def self.without_prefix(website)
        website = website.gsub("http://", "").gsub("https://", "")
        website.gsub("www.", "")
      end

      def self.extract_person_info(person)
        formatted_person = {
          "name" => person["FullName"],
          "phone_number" => person["Phone"],
          "email" => person["Email"]
        }
        formatted_person["positions"] = Utils.format_position(person["Title"]) if person["Title"].present?

        formatted_person
      end
    end
  end
end
