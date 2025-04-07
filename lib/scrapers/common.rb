# frozen_string_literal: true

require_relative "../tasks/city_scrape/city_manager"

module Scrapers
  module Common
    def self.missing_contact_info?(person)
      email = person["contact_details"].find { |detail| detail["type"] == "email" }
      phone = person["contact_details"].find { |detail| detail["type"] == "phone" }
      email.blank? && phone.blank?
    end

    def self.format_url(url)
      # get rid of any trailing slashes
      url = url.gsub(%r{/$}, "")
      # get rid of any trailing spaces
      url = url.gsub(/\s+$/, "")
      # get rid of spaces
      url.gsub(" ", "%20")
      Addressable::URI.parse(url).to_s
    end

    def self.urls_without_keywords(url_pairs, keywords)
      url_pairs.select do |url, _text|
        keywords.none? { |keyword| url.downcase.include?(keyword.downcase) }
      end
    end

    def self.urls_without_dates(url_pairs)
      url_pairs.reject do |url|
        uri = URI.parse(url)
        path = uri.path

        # Check for date patterns (YYYY/MM/DD) in the URL path
        path.match?(%r{/\d{4}/\d{2}/\d{2}/})
      end
    end
  end
end
