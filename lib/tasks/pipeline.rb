# frozen_string_literal: true

require_relative "../services/brave"
require_relative "../services/openai"
require_relative "../scrapers/places"
require_relative "../scrapers/common"
require_relative "../core/municipal_scraper"
require_relative "../core/page_fetcher"
require_relative "../tasks/city_scrape/state_manager"
require_relative "../core/search_router"
require_relative "../core/people_manager"
require_relative "../scrapers/local_officials_scraper"
require_relative "../services/spaces"

namespace :pipeline do
  desc "Pick cities from queue"
  task :pick_cities, [:state, :num_cities, :gnis_to_ignore] do |_t, args| # bug -- this is a list of city names, which is not a unique identifier
    state = args[:state]
    num_cities = args[:num_cities]
    gnis_to_ignore = args[:gnis_to_ignore].present? ? args[:gnis_to_ignore].split(" ") : []

    state_places = CityScrape::StateManager.get_state_places(state)

    cities = state_places["places"].select do |c|
      !gnis_to_ignore.include?(c["gnis"]) &&
        c["website"].present? &&
        (c["meta_sources"].blank? || c["meta_sources"].count == 1) # If there's only one source, we can assume it's a state source
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
    city_context = {
      state: state,
      city_entry: city_entry,
      government_type: Core::CityManager::GOVERNMENT_TYPE_MAYOR_COUNCIL
    }

    create_prepare_directories(state, city_entry)

    fetch_with_state_source(city_context) # State-level city directory source

    # OpenAI - LLM call
    page_fetcher, source_urls = fetch_with_openai(city_context)

    ## Gemini - LLM call
    fetch_with_gemini(city_context, page_fetcher, source_urls)

    aggregate_sources(city_context, sources: %w[state_source gemini openai])
    # Create config.yml for the city
    create_config_yml(state, city_entry)

    people = Core::PeopleManager.get_people(state, gnis)
    # ~3remove_unused_cache_folders(state, city_entry, people)
  end

  def fetch_with_state_source(municipality_context)
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])

    # This call can fail if the state source is down (e.g. MRSC.org for WA)
    begin
      source_city_people = Scrapers::LocalOfficialScraper.fetch_with_state_source(municipality_context)
      Core::PeopleManager.update_people(municipality_context[:state], municipality_context[:city_entry],
                                        source_city_people, "state_source.before")
      formatted_source_city_people = Core::PeopleManager.format_people(source_city_people, positions_config)
      Core::PeopleManager.update_people(municipality_context[:state], municipality_context[:city_entry],
                                        formatted_source_city_people, "state_source.after")
    rescue StandardError => e
      puts "Error pulling from state source: #{e}"
      puts "Backtrace: #{e.backtrace}"
    end
  end

  def fetch_with_openai(municipality_context)
    state = municipality_context[:state]
    city_entry = municipality_context[:city_entry]
    gnis = municipality_context[:city_entry]["gnis"]
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])

    config_file = File.join(PathHelper.get_data_source_city_path(state, gnis), "config.yml")
    config_content = { "scrape_sources" => [] }
    config_content = YAML.load_file(config_file) if File.exist?(config_file)

    page_fetcher, source_dirs, openai_people = Core::MunicipalScraper.fetch(
      "openai",
      municipality_context,
      cached_urls: config_content["scrape_sources"]
    )
    Core::PeopleManager.update_people(state, city_entry, openai_people, "openai.before")
    formatted_openai_people = Core::PeopleManager.format_people(openai_people, positions_config)
    Core::PeopleManager.update_people(state, city_entry, formatted_openai_people, "openai.after")

    # This is the only call that scrapes images
    people_with_images = process_images(municipality_context, source_dirs, formatted_openai_people)
    Core::PeopleManager.update_people(state, city_entry, people_with_images, "openai.after")
    sources = formatted_openai_people.map { |person| person["sources"] }.flatten.uniq

    [page_fetcher, sources]
  end

  def fetch_with_gemini(municipality_context, page_fetcher, cached_urls)
    state = municipality_context[:state]
    city_entry = municipality_context[:city_entry]
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])

    _page_fetcher, _source_dirs, gemini_people = Core::MunicipalScraper.fetch(
      "gemini",
      municipality_context,
      page_fetcher: page_fetcher,
      cached_urls: cached_urls
    )
    Core::PeopleManager.update_people(state, city_entry, gemini_people, "gemini.before")
    formatted_gemini_people = Core::PeopleManager.format_people(gemini_people, positions_config)
    Core::PeopleManager.update_people(state, city_entry, formatted_gemini_people, "gemini.after")
  end

  def aggregate_sources(municipality_context, sources: [])
    state = municipality_context[:state]
    city_entry = municipality_context[:city_entry]
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])
    validated_result = Validators::CityPeople.validate_sources(state, city_entry["gnis"])

    combined_people = validated_result[:merged_sources]
    formatted_people = Core::PeopleManager.format_people(combined_people, positions_config)

    Core::PeopleManager.update_people(state, city_entry, formatted_people)

    city_people_hash = Digest::MD5.hexdigest(combined_people.to_yaml)
    CityScrape::StateManager.update_state_places(state, [
                                                   { "gnis" => city_entry["gnis"],
                                                     "meta_updated_at" => Time.now
                                                      .in_time_zone("America/Los_Angeles")
                                                      .strftime("%Y-%m-%d"),
                                                     "meta_hash" => city_people_hash,
                                                     "meta_sources" => sources }
                                                 ])
  end

  def create_config_yml(state, city_entry)
    gnis = city_entry["gnis"]
    people = Core::PeopleManager.get_people(state, gnis)
    config_yml = {
      "scrape_sources" => people.map { |person| person["sources"] }.flatten.uniq
    }

    config_path = File.join(PathHelper.get_data_source_city_path(state, city_entry["gnis"]), "config.yml")
    File.write(config_path, config_yml.to_yaml)
  end

  def create_prepare_directories(state, city_entry)
    cache_destination_dir = PathHelper.get_city_cache_path(state, city_entry["gnis"])

    # Remove cache folder if it exists
    FileUtils.rm_rf(cache_destination_dir) if Dir.exist?(cache_destination_dir)
    FileUtils.mkdir_p(cache_destination_dir)
  end

  def process_images(municipality_context, source_dirs, people)
    state = municipality_context[:state]
    city_entry = municipality_context[:city_entry]
    puts "Uploading images for #{city_entry["name"]}"
    puts "Source dirs: #{source_dirs.inspect}"

    data_city_path = PathHelper.get_data_city_path(state, city_entry["gnis"])
    # Find last instance of data/ because repo could start with open-data/data/
    remote_city_path = data_city_path.rpartition("data/").last

    images_in_use = people.map { |person| person["image"] }.compact

    source_dirs.each do |source_dir|
      # Get list of images in dir
      source_images_dir = File.join(source_dir, "images")
      source_dir_images = Dir.entries(source_images_dir)

      filtered_images = source_dir_images.select do |image_filename|
        images_in_use.any? { |image_path| File.basename(image_path) == File.basename(image_filename) }
      end

      filtered_images.each do |filtered_image|
        file_path = File.join(source_images_dir, filtered_image)
        file_key = File.join(remote_city_path, "images", filtered_image)
        puts "Uploading #{file_path} to remote #{file_key}"
        content_type = Utils::ImageHelper.determine_mime_type(file_path)
        Services::Spaces.put_object(file_key, file_path, content_type)
      end

      # Cleanup images
      FileUtils.rm_rf(source_images_dir)
      Dir.mkdir(source_images_dir)
    end

    # Update sources with remote URLs
    people.map do |person|
      next if person["image"].blank?

      key = File.join(remote_city_path, "images", File.basename(person["image"]))
      person["image"] = Utils::ImageHelper.get_cdn_url(key)

      person
    end
  end

  def self.remove_unused_cache_folders(state, city_entry, people)
    gnis = city_entry["gnis"]
    cache_dir = PathHelper.get_city_cache_path(state, gnis)
    cache_folders = Pathname.new(cache_dir).children.select(&:directory?).collect(&:to_s)

    # Get list of src files in use
    source_urls = people.flat_map do |person|
      person["sources"]
        .map { |source| Utils::UrlHelper.url_to_safe_folder_name(source) }
    end.uniq

    cache_folders.each do |cache_folder|
      unless source_urls.any? { |source_url| cache_folder.include?(source_url) }
        puts "Removing #{cache_folder} from cache"
        FileUtils.rm_rf(cache_folder)
      end
    end
  end
end
