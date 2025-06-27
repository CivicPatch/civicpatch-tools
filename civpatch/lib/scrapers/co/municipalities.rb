require "core/browser"

module Scrapers
  module Co
    class Municipalities
      URL = "https://www.cml.org/utility-pages/cml-member-directory"
      def self.fetch
          puts "Fetching Colorado Municipal League Directory from #{URL}"
          fetch_directory()
      end

      def self.fetch_directory
        # html = Core::Browser.fetch_page_content(URL)
        cached_directory_path = Core::PathHelper.project_path(File.join("lib", "scrapers", "co", "cache", "directory.html"))
        html = File.read(cached_directory_path)
        document = Nokolexbor::HTML(html)

        directory = {}
        document.css("ul li").each do |li|
          municipality_name = li.text.strip.gsub("*", "").strip # Ensure whitespace is trimmed after removing "*"
          website = li.at_css("a")&.attr("href")

          next unless municipality_name.present?

          directory[municipality_name] = {
            "name" => municipality_name,
            "website" => website,
            "government_type" => "mayor_council" # Default assumption, can be updated later
          }

        end

        directory
      end
    end
  end
end