# frozen_string_literal: true

require_relative "../tasks/city_scrape/city_manager"

module Scrapers
  module Common
    def self.missing_contact_info?(person)
      email = person["contact_details"].find { |detail| detail["type"] == "email" }
      phone = person["contact_details"].find { |detail| detail["type"] == "phone" }
      email.blank? && phone.blank?
    end

    def self.prune_unused_images(state, city_entry)
      # Get list of all images in the data/<state> directory
      city_path = CityScrape::CityManager.get_city_path(state, city_entry)
      all_images = Dir.glob(File.join(city_path, "images", "*"))

      # Get list of all images in the data/<state>/<city> directory
      images_in_use = []
      city_directory = CityScrape::CityManager.get_city_directory(state, city_entry)
      city_directory["people"].each do |person|
        images_in_use << File.join(city_path, person["image"]) if person["image"].present?
      end

      # Delete all images that are not in use
      all_images.each do |image|
        File.delete(image) unless images_in_use.include?(image)
      end
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
  end
end
