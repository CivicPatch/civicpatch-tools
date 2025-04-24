require "core/browser"
require "utils/phone_helper"
require "utils/url_helper"

module Scrapers
  module Or
    class Municipalities
      WEBSITE_SOURCE_URL = "https://sos.oregon.gov/blue-book/Pages/local/cities.aspx".freeze
      STATE_SOURCE_URL = "https://www.orcities.org/resources/reference/city-directory"
      STATE_SOURCE_MUNICIPAL_URL = "https://www.orcities.org/resources/reference/city-directory/details"

      def self.fetch
        sos_directory = fetch_sos_directory(WEBSITE_SOURCE_URL)

        sos_directory.each_with_object({}) do |sos_municipality_link, hash|
          puts "Fetching data from #{sos_municipality_link["name"]} at #{sos_municipality_link["url"]}"
          municipality_data = fetch_sos_municipality_data(sos_municipality_link["url"])
          hash[sos_municipality_link["name"]] = municipality_data
        end
      end

      def self.fetch_sos_municipality_data(url)
        response = Browser.fetch_html(url)

        html = Nokogiri::HTML(response)

        # Address: Find div containing direct text node with 'Address:'
        # Use gsub to robustly remove label and potential leading junk
        address_node = html.at_xpath("//div[contains(text(), 'Address:')]")
        address = address_node ? address_node.text.gsub(/\A[^A-Z]*Address:\s*/, "").strip : nil

        # Phone: Find div containing text starting with 'Phone:' (handles nesting)
        # Use gsub to robustly remove label and potential leading junk
        phone_node = html.at_xpath("//div[contains(., 'Phone:')]") # Find a div containing Phone:
        # Extract text only from the most specific node containing the number
        phone_text = phone_node&.xpath(".//text()[contains(., 'Phone:')]")&.first&.text
        phone_number = phone_text ? phone_text.gsub(/\A[^0-9(]*Phone:\s*/, "").gsub(/[^0-9]$/, "").strip : nil

        # Web: Find the <a> tag immediately following text containing 'Web:'
        website_link_node = html.at_xpath("//text()[contains(., 'Web:')]/following-sibling::a[1][@href]")
        website = website_link_node ? website_link_node["href"].strip : nil

        # Email: Find the <a> tag immediately following text containing 'Email:' (ensure mailto)
        email_link_node = html.at_xpath("//text()[contains(., 'Email:')]/following-sibling::a[1][starts-with(@href, 'mailto:')]")
        email = email_link_node ? email_link_node["href"].sub(/^mailto:/, "").strip : nil

        {
          "address" => address,
          "phone_number" => Utils::PhoneHelper.format_phone_number(phone_number),
          "website" => Utils::UrlHelper.format_url(website),
          "email" => email
        }
      end

      def self.fetch_sos_directory(url)
        response = Browser.fetch_html(url)
        html = Nokogiri::HTML(response)

        municipalities = html.css(".cities ul a").map do |link|
          {
            "name" => link.text.strip,
            "url" => link["href"]
          }
        end

        if municipalities.empty?
          puts "No municipalities found"
          return []
        end

        municipalities
      end
    end
  end
end
