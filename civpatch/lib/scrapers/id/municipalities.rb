require "services/wikipedia"

# Idaho municipalities are legally called cities

module Scrapers
  module Id
    class Municipalities

      def self.fetch
        fetch_directory()
      end

      def self.fetch_directory
        rows = Services::Wikipedia.fetch_municipalities("List_of_municipalities_in_Idaho", {municipality_name: 1, county_names: 5, row_start: 1})
        directory = {}

        rows.each do |row|
          municipality_name = row["name"]
          directory[municipality_name] = {
            "name" => municipality_name,
            "counties" => row["counties"],
            "website" => row["website"],
            "fips" => row["fips"]
          }
        end

        directory
      end
    end
  end
end