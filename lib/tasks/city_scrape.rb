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
require_relative "../tasks/city_scrape/city_manager"
require_relative "../tasks/city_scrape/search_manager"
require_relative "../tasks/city_scrape/page_processor"
require_relative "../tasks/city_scrape/state_manager"
require_relative "../tasks/city_scrape/person_manager"

namespace :city_scrape do
  desc "Pick cities from queue"
  task :pick_cities, [:state, :num_cities, :gnis_to_ignore] do |_t, args| # bug -- this is a list of city names, which is not a unique identifier
    state = args[:state]
    num_cities = args[:num_cities]
    gnis_to_ignore = args[:gnis_to_ignore].present? ? args[:gnis_to_ignore].split(" ") : []

    state_places = CityScrape::StateManager.get_state_places(state)

    cities = state_places["places"].select do |c|
      !gnis_to_ignore.include?(c["gnis"]) &&
        c["last_city_scrape_run"].nil? && c["website"].present?
    end.first(num_cities.to_i)

    puts cities.map { |c| { "name": c["name"], "gnis": c["gnis"], "county": c["counties"].first } }.to_json
  end

  desc "Find official cities for a state"
  task :get_places, [:state] do |_t, args|
    if args[:state].blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:get_places[state]'"
      puts "Example: rake 'city_info:get_places[wa]'"
      exit 1
    end

    state = args[:state]

    new_places = Scrapers::Places.fetch_places(state)
    CityScrape::StateManager.update_state_places(state, new_places)
  end

  desc "Extract city info for a specific city"
  task :fetch, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    create_prepare_directories(state, city_entry)

    openai_service = Services::Openai.new
    data_fetcher = Scrapers::DataFetcher.new

    source_dirs, city_directory = build_city_directory(%w[manual brave], state, city_entry, openai_service,
                                                       data_fetcher)
    finalize_city_directory(state, city_entry, city_directory, source_dirs)
  end

  desc "Get member info. Initial council member did not collect enough info,
   but if members have a website, we can probably get more info"
  task :get_member_info, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    # TODO: this is doing too much, too many files moving around in one function too...
    CityScrape::PersonManager.fetch_people_info(state, gnis)
  end

  def create_prepare_directories(state, city_entry)
    city_path = CityScrape::CityManager.get_city_path(state, city_entry)
    cache_destination_dir = File.join(city_path, "cache")

    FileUtils.mkdir_p(cache_destination_dir)
    FileUtils.rm_rf(File.join(city_path, "city_scrape_sources", "*"))
  end

  def copy_source_files(
    state,
    city_entry,
    source_dirs
  )
    city_path = CityScrape::CityManager.get_city_path(state, city_entry)
    sources_destination_dir = File.join(city_path, "city_scrape_sources")

    images_dir = File.join(city_path, "images")
    FileUtils.mkdir_p(images_dir)

    source_dirs.each do |source_dir|
      # Copy all images from source to destination
      puts "Copying images from #{source_dir}/images to #{images_dir}"
      source_image_dir = File.join(source_dir, "images")

      if Dir.exist?(source_image_dir) && !Dir.empty?(source_image_dir)
        Dir.glob(File.join(source_image_dir, "*")).each do |file|
          FileUtils.cp_r(file, images_dir, remove_destination: true)
        end
      end

      FileUtils.rm_rf(sources_destination_dir) if Dir.exist?(sources_destination_dir)
      FileUtils.mv(source_dir, sources_destination_dir)
    end
  end

  def finalize_city_directory(state, city_entry, new_city_directory, source_dirs)
    city_path = CityScrape::CityManager.get_city_path(state, city_entry)
    cache_directory = File.join(city_path, "cache")

    copy_source_files(state, city_entry, source_dirs)

    CityScrape::CityManager.update_city_directory(state, city_entry, new_city_directory)
    CityScrape::StateManager.update_state_places(state, [
                                                   { "gnis" => city_entry["gnis"],
                                                     "last_member_info_scrape_run" => Time.now.strftime("%Y-%m-%d") }
                                                 ])
    FileUtils.rm_rf(cache_directory)

    Scrapers::Common.prune_unused_images(state, city_entry)
  end

  def build_city_directory(search_engines, state, city_entry, openai_service, data_fetcher)
    search_results_processed = []
    local_source_dirs = []
    city_directory = { "people" => [] }

    search_engines.each do |engine|
      search_result_urls = CityScrape::SearchManager.fetch_search_results(engine, state, city_entry)
      search_results_to_process = search_result_urls - search_results_processed
      puts "Engine #{engine} found #{search_result_urls.count} search results for #{city_entry["name"]}"
      puts "Search results to process: #{search_results_to_process.count}"
      puts "#{search_results_to_process.join("\n")}"

      page_processor = CityScrape::PageProcessor.new(state, engine, openai_service, data_fetcher, city_entry,
                                                     city_directory)

      new_local_source_dirs, city_directory = page_processor.process_pages(search_results_to_process)

      search_results_processed += search_results_to_process
      local_source_dirs += new_local_source_dirs

      return [local_source_dirs, city_directory] if CityScrape::CityManager.valid_city_directory?(city_directory)
    end

    [local_source_dirs, city_directory]
  end
end
