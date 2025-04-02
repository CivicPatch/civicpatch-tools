# frozen_string_literal: true

require_relative "../scrapers/common"

namespace :city_scrape do
  desc "Count all cities without fips"
  task :count_cities_without_fips do
    state_directory_file = PathHelper.project_path(File.join("data", "wa", "places.yml"))
    state_directory = YAML.load(File.read(state_directory_file))
    without_fips =  state_directory["places"].select { |p| p["fips"].blank? }
    without_gnis =  state_directory["places"].select { |p| p["gnis"].blank? }
    puts without_fips.count
    puts without_fips.map { |p| p["name"] }.join(", ")
    puts without_gnis.count
    puts without_gnis.map { |p| p["name"] }.join(", ")
  end
end
