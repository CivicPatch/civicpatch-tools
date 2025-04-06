# frozen_string_literal: true

module Scrapers
  class Utils
    def self.prune_unused_images(state, gnis)
      # Get list of all images in the data/<state> directory
      city_path = PathHelper.get_city_path(state, gnis)
      all_images = Dir.glob(File.join(city_path, "images", "*"))

      # Get list of all images in the data/<state>/<city>/directories/directory_scrape.yml directory
      # That is the only directory that should have images
      images_in_use = []
      directory = PathHelper.get_city_people_candidates_file_path(state, gnis, "scrape.before")

      return unless File.exist?(directory)

      directory_data = YAML.load(File.read(directory))
      directory_data.each do |person|
        images_in_use << File.join(city_path, person["image"]) if person["image"].present?
      end

      # Delete all images that are not in use
      all_images.each do |image|
        File.delete(image) unless images_in_use.include?(image)
      end
    end
  end
end
