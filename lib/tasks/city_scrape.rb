# frozen_string_literal: true

# This file contains rake tasks and supporting code for scraping city council information.
# It handles:
# - Finding and selecting cities to process
# - Scraping council member data from city websites
# - Managing the storage and organization of city data
# - Generating PR comments with results
#
# Main tasks:
# - city_scrape:pick_cities[state,num_cities]    # Select next batch of cities to process
# - city_scrape:get_places[state]                # Find official cities for a state
# - city_scrape:fetch[state,gnis]                # Extract city council info
# - city_scrape:get_member_info[state,gnis]      # Get additional member details
# - city_scrape:get_pr_comment[state,gnis,branch]# Generate markdown for PR
#
# Example usage:
# rake 'city_scrape:fetch[wa,2410494]'          # Fetch info for Federal Way, WA

# rake 'city_info:extract[wa,seattle,https://www.seattle.gov/council/meet-the-council]'
# rake 'city_info:extract[tx,austin,https://www.austintexas.gov/austin-city-council]'
# rake 'city_info:extract[nm,albuquerque,https://www.cabq.gov/council/find-your-councilor]'
# rake 'city_info:get_meta[wa,seattle]'
# rake 'city_info:find_geojson[nm,albuquerque,district]'

require_relative "../services/brave"
require_relative "../services/openai"
require_relative "../scrapers/places"
require_relative "../scrapers/data_fetcher"
require_relative "../scrapers/common"
require_relative "../scrapers/utils"
require_relative "../core/city_scraper/people_scraper"
require_relative "../tasks/city_scrape/city_manager"
require_relative "../tasks/city_scrape/state_manager"
require_relative "../core/search_router"
require_relative "../sources/state_source/city_people"
require_relative "../core/people_manager"

namespace :city_scrape do
  desc "Pick cities from queue"
  task :pick_cities, [:state, :num_cities, :gnis_to_ignore] do |_t, args| # bug -- this is a list of city names, which is not a unique identifier
    state = args[:state]
    num_cities = args[:num_cities]
    gnis_to_ignore = args[:gnis_to_ignore].present? ? args[:gnis_to_ignore].split(" ") : []

    state_places = CityScrape::StateManager.get_state_places(state)

    cities = state_places["places"].select do |c|
      !gnis_to_ignore.include?(c["gnis"]) &&
        c["meta_updated_at"].nil? && c["website"].present?
    end.first(num_cities.to_i)

    puts cities.map { |c| { "name": c["name"], "gnis": c["gnis"], "county": c["counties"].first } }.to_json
  end

  desc "Find official cities for a state"
  task :get_places, [:state] do |_t, args|
    raise "Missing required parameter: state" if args[:state].blank?

    state = args[:state]

    new_places = Scrapers::Places.fetch_places(state)
    CityScrape::StateManager.update_state_places(state, new_places)
  end

  desc "Scrape city info for a specific city"
  task :fetch, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    create_prepare_directories(state, city_entry)

    config = Core::CityManager.get_positions(Core::CityManager::GOVERNMENT_TYPE_MAYOR_COUNCIL)

    # Official Source
    source_city_people = Sources::StateSource::CityPeople.get_city_people(state, gnis)
    Core::PeopleManager.update_people(state, city_entry, source_city_people, "state_source.before")
    formatted_source_city_people = Core::PeopleManager.format_people(source_city_people, config)
    Core::PeopleManager.update_people(state, city_entry, formatted_source_city_people, "state_source.after")

    ### Web Scrape Source
    openai_source_dirs, openai_people = CityScraper::PeopleScraper.fetch("gpt", state, gnis, config)
    Core::PeopleManager.update_people(state, city_entry, openai_people, "scrape.before")
    formatted_openai_people = Core::PeopleManager.format_people(openai_people, config)
    Core::PeopleManager.update_people(state, city_entry, formatted_openai_people, "scrape.after")

    # TODO: Would like to use a SERP API to get the URLs for city directories instead
    seeded_urls = formatted_openai_people.map do |person|
      person["sources"]
    end.uniq.flatten

    ## Gemini Source
    gemini_source_dirs, gemini_city_people = CityScraper::PeopleScraper.fetch("google_gemini", state, gnis, config,
                                                                              %w[seeded brave manual], seeded_urls)

    Core::PeopleManager.update_people(state, city_entry, gemini_city_people, "google_gemini.before")
    formatted_gemini_city_people = Core::PeopleManager.format_people(gemini_city_people, config)
    Core::PeopleManager.update_people(state, city_entry, formatted_gemini_city_people, "google_gemini.after")

    validated_result = Validators::CityPeople.validate_sources(state, gnis)

    combined_people = validated_result[:merged_sources]
    formatted_people = Core::PeopleManager.format_people(combined_people, config)

    Core::PeopleManager.update_people(state, city_entry, formatted_people)

    # Move images into the right places
    source_dirs = openai_source_dirs + gemini_source_dirs
    copy_source_files(state, city_entry, source_dirs, formatted_people)

    city_people_hash = Digest::MD5.hexdigest(combined_people.to_json)
    CityScrape::StateManager.update_state_places(state, [
                                                   { "gnis" => city_entry["gnis"],
                                                     "meta_updated_at" => Time.now
                                                      .in_time_zone("America/Los_Angeles")
                                                      .strftime("%Y-%m-%d"),
                                                     "meta_hash" => city_people_hash }
                                                 ])
  end

  def create_prepare_directories(state, city_entry)
    cache_destination_dir = PathHelper.get_city_cache_path(state, city_entry["gnis"])

    FileUtils.mkdir_p(cache_destination_dir)
  end

  def copy_source_files(
    state,
    city_entry,
    source_dirs,
    people
  )
    puts "Copying source files for #{city_entry["name"]}"
    puts "Source dirs: #{source_dirs.inspect}"

    final_city_path = PathHelper.get_data_city_path(state, city_entry["gnis"])

    images_dir = File.join(final_city_path, "images")
    Dir.rmdir(images_dir) if Dir.exist?(images_dir)

    FileUtils.mkdir_p(images_dir)
    images_in_use = people.map { |person| person["image"] }
    puts "imagse in use: #{images_in_use}"

    source_dirs.each do |source_dir|
      # Get list of images in dir
      source_images_dir = File.join(source_dir, "images")
      source_dir_images = Dir.entries(source_images_dir)

      filtered_images = source_dir_images.select do |image_filename|
        images_in_use.any? { |image_path| image_path.include?(image_filename) }
      end

      filtered_images.each do |filtered_image|
        FileUtils.cp(filtered_image, images_dir)
      end
    end
  end
end
