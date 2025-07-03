# frozen_string_literal: true

require "services/wikipedia"

module Scrapers
  module Nd
    class Municipalities
      URL = "https://www.nd.gov/government/local-government/city-website-list"

      def self.fetch
        puts "Fetching North Dakota Municipalities from #{URL}"

        results = fetch_directory()
        length = results.length
        puts "Found #{length} municipalities in North Dakota"
        results
      end

      def self.fetch_directory
        response = HTTParty.get(URL)# , verify: false)
        html = response.body
        document = Nokogiri::HTML(html)
        document.css("div.field--name-field-wysiwyg-text ul li a").each_with_object({}) do |link, directory|
          municipality_name = link.text.strip
          next if municipality_name.empty?

          website = link.attr("href")
          directory[municipality_name] = {
            "name" => municipality_name,
            "website" => website,
            "government_type" => "mayor_council" # Default assumption, can be updated later
          }
        end
      end
    end
  end
end