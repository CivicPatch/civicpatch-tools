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

require_relative "../scrapers/city"
require_relative "../services/brave"
require_relative "../services/openai"
require_relative "../scrapers/us/wa/places"
require_relative "../scrapers/us/mi/places"
require_relative "../scrapers/site_crawler"
require_relative "../scrapers/data_fetcher"
require_relative "../scrapers/common"

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

    scraper = case state
              when "wa"
                Scrapers::Us::Wa::Directory
              when "mi"
                Scrapers::Us::Mi::Directory
              else
                raise "Unsupported state: #{state}"
    end

    new_places = scraper.fetch_places
    CityScrape::StateManager.update_state_places(state, new_places)
  end

  desc "Extract city info for a specific city"
  task :fetch, [:state, :gnis] do |_t, args|
    state_city_entry = validate_fetch_inputs(args[:state], args[:gnis])
    prepare_directories(args[:state], state_city_entry)

    openai_service = Services::Openai.new
    data_fetcher = Scrapers::DataFetcher.new

    source_dirs, city_directory = build_city_directory(%w[manual brave], state, state_city_entry, openai_service, data_fetcher)
    finalize_city_directory(state, state_city_entry, city_directory, source_dirs)
  end

  desc "Get member info. Initial council member did not collect enough info,
   but if members have a website, we can probably get more info"
  task :get_member_info, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    data_fetcher = Scrapers::DataFetcher.new
    openai_service = Services::Openai.new

    state_city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)

    raise "City entry not found for #{gnis} in #{state}" unless state_city_entry.present?

    city_data = CityScrape::StateManager.get_city_directory(state, state_city_entry)

    city_data["people"].each do |person|
      next if person["website"].present? && Scrapers::Common.missing_contact_info?(person)

      puts "Processing #{person["name"]}"
      content_file = data_fetcher.extract_content(person["website"], candidate_dir)
      person_info = extract_city_info(openai_service, content_file, person["website"])
      File.write("chat.txt", "old person info: #{person.inspect}\nnew person info: #{person_info.inspect}\n\n",
                 mode: "a")
      #person.merge!(person_info)
    end

    # Write the updated city directory back to the file
    File.write(get_city_directory_file(state, state_city_entry), city_data.to_yaml)

    CityScrape::StateManager.update_state_places(state, [
                                                   { "gnis" => state_city_entry["gnis"],
                                                     "last_member_info_scrape_run" => Time.now.strftime("%Y-%m-%d") }
                                                 ])
  end 

  def get_state_places_file(state)
    PathHelper.project_path(File.join("data", "us", state, "places.yml"))
  end

  def create_prepare_directories(state, city_entry)
    city_path = CityScrape::CityManager.get_city_path(state, city_entry)
    cache_destination_dir = File.join(city_path, "cache")

    FileUtils.mkdir_p(cache_destination_dir)
    FileUtils.rm_rf(File.join(city_path, "city_scrape_sources", "*"))
  end

  def fetch_content(data_fetcher, url, candidate_dir)
    data_fetcher.extract_content(url, candidate_dir)
  rescue StandardError => e
    puts "Error fetch_content: #{e.message}"
    puts "Error backtrace: #{e.backtrace.join("\n")}"
    nil
  end

  def extract_city_info(openai_service, content_file, url)
    updated_city_info = openai_service.extract_city_info(content_file, url)

    if updated_city_info.is_a?(Hash) && updated_city_info.key?("error")
      nil
    else
      updated_city_info["council_url_site"] = url
      updated_city_info
    end
  end

  def copy_source_files(
    state,
    city_entry,
    source_dirs
  )
    city_path = CityScrape::CityManager.get_city_path(state, city_entry)
    sources_destination_dir = File.join(city_path, "city_scrape_sources")
    FileUtils.mkdir_p(sources_destination_dir)

    images_dir = File.join(city_path, "images")
    FileUtils.mkdir_p(images_dir)

    source_dirs.each do |source_dir|
      # store images in combined images directory
      puts "Copying images from #{source_dir}/images/* to #{images_dir}"
      Dir.glob("#{source_dir}/images/*").each do |image|
        FileUtils.cp(image, images_dir)
      end

      FileUtils.mv(source_dir, sources_destination_dir)
    end
  end

  def finalize_city_directory(state, city_entry, new_city_directory, source_dirs)
    city_path = CityScrape::CityManager.get_city_path(state, city_entry)
    cache_directory = File.join(city_path, "cache")

    copy_source_files(state, city_entry, source_dirs)

    CityScrape::CityManager.update_city_directory(state, city_entry, new_city_directory)
    FileUtils.rm_rf(cache_directory)
  end

  def build_city_directory(search_engines, state, state_city_entry, openai_service, data_fetcher)
    search_result_urls = []
    local_source_dirs = []
    city_directory = { "people" => [], "sources" => [] }

    search_engines.each do |engine|
      search_result_urls = CityScrape::SearchManager.fetch_search_results(engine, state, state_city_entry)
      success, new_local_source_dirs, city_directory = process_search_results(
        engine, search_result_urls, openai_service, data_fetcher, city_directory
      )
      local_source_dirs += new_local_source_dirs

      return [local_source_dirs, city_directory] if success
    end

    [local_source_dirs, city_directory]
  end

  def process_search_results(engine, search_result_urls, openai_service, data_fetcher, city_directory)
    found_valid_directory = false
    source_dirs = []

    search_result_urls.each_with_index.map do |url, index|
      partial_city_directory, candidate_dir = CityScrape::PageProcessor.new(state, engine, openai_service, data_fetcher, state_city_entry).process_page(url, index)
      next unless CityScrape::CityManager.includes_people?(partial_city_directory)

      city_directory = CityScrape::CityManager.merge_directory(city_directory, partial_city_directory, url)
      source_dirs << candidate_dir

      found_valid_directory = CityScrape::CityManager.valid_city_directory?(city_directory)
      break if found_valid_directory
    end

    [found_valid_directory, source_dirs, city_directory]
  end

  def validate_fetch_inputs(state, gnis)
    state_city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
    raise "City entry not found for #{gnis} in #{state}" unless state_city_entry.present?
    state_city_entry
  end

  def prepare_directories(state, state_city_entry)
    cache_directory = create_prepare_directories(state, state_city_entry)
    city_directory = { "people" => [], "sources" => [] }
    [cache_directory, city_directory]
  end
end
