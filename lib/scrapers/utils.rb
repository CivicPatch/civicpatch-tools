# frozen_string_literal: true

module Scrapers
  class Utils
    def self.prune_unused_images(state, gnis)
      # Get list of all images in the data_source/<state>/city directory
      city_path = PathHelper.get_data_city_path(state, gnis)
      all_images = Dir.glob(File.join(city_path, "images", "*"))

      # Get list of all images in the data/<state>/<city>/people/directory_scrape.yml directory
      # That is the only file that should have images
      images_in_use = []
      people = PathHelper.get_people_candidates_file_path(state, gnis, "scrape.before")

      return unless File.exist?(people)

      people_data = JSON.parse(File.read(people))
      people_data.each do |person|
        images_in_use << File.join(city_path, person["image"]) if person["image"].present?
      end

      # Delete all images that are not in use
      all_images.each do |image|
        File.delete(image) unless images_in_use.include?(image)
      end
    end
  end
end
