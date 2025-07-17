require "services/wikipedia"

module Scrapers
  module Ca
    class Municipalities

      def self.fetch
        fetch_directory()
      end

      def self.fetch_directory
        rows = Services::Wikipedia.fetch_municipalities("List_of_municipalities_in_California", {table_index: 1, municipality_name: 0, county_names: 2, row_start: 2})
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