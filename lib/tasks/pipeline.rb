# frozen_string_literal: true

require_relative "../services/brave"
require_relative "../services/openai"
require_relative "../core/municipal_scraper"
require_relative "../core/page_fetcher"
require_relative "../core/state_manager"
require_relative "../core/search_router"
require_relative "../core/people_manager"
require_relative "../core/person_resolver"
require_relative "../core/config_manager"
require_relative "../services/spaces"
require_relative "../scrapers/municipalities"
require_relative "../scrapers/municipality_officials"

namespace :pipeline do
  desc "Pick cities from queue"
  task :pick_cities, [:state, :num_cities, :gnis_to_ignore] do |_t, args| # bug -- this is a list of city names, which is not a unique identifier
    state = args[:state]
    num_cities = args[:num_cities]
    gnis_to_ignore = args[:gnis_to_ignore].present? ? args[:gnis_to_ignore].split(" ") : []

    state_places = Core::StateManager.get_municipalities(state)

    cities = state_places["municipalities"].select do |c|
      !gnis_to_ignore.include?(c["gnis"]) &&
        c["website"].present? &&
        (c["meta_sources"].blank? || c["meta_sources"].count == 1) # If there's only one source, we can assume it's a state source
    end.first(num_cities.to_i)

    puts cities.map { |c|
      { "name": c["name"].gsub(" ", "_"), "gnis": c["gnis"], "county": c["counties"].first }
    }.to_json
  end

  desc "Scrape city info for a specific city"
  task :fetch, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    municipality_context = Core::ContextManager.get_context(state, gnis)

    prepare_directories(state, municipality_context[:municipality_entry])

    source_directory_list_config, people_config = fetch_with_state_source(municipality_context) # State-level city directory source
    municipality_context = Core::ContextManager.update_context_config(municipality_context,
                                                                      source_directory_list: source_directory_list_config,
                                                                      people: people_config)

    people_config = fetch_with_scrape(municipality_context)
    municipality_context = Core::ContextManager.update_context_config(municipality_context,
                                                                      people: people_config)

    scrape_sources = aggregate_sources(municipality_context, sources: %w[state_source gemini openai])
    municipality_context = Core::ContextManager.update_context_config(municipality_context,
                                                                      scrape_sources: scrape_sources)

    people = Core::PeopleManager.get_people(state, gnis)
    remove_unused_cache_folders(municipality_context, people)

    Core::ConfigManager.cleanup(state, gnis, municipality_context[:config])
  end

  desc "Fetch city officials from state source"
  task :fetch_from_state, [:state] do |_t, args|
    state = args[:state]
    config = Core::ConfigManager.get_config(state, gnis)

    municipalities = Core::StateManager.get_municipalities(state)["municipalities"]
    municipalities.each do |municipality_entry|
      municipality_context = {
        config: config,
        state: state,
        municipality_entry: municipality_entry,
        government_type: Scrapers::Municipalities.get_government_type(state, municipality_entry)
      }
      fetch_with_state_source(municipality_context)
      aggregate_sources(municipality_context, sources: %w[state_source])
    end
  end

  desc "Find municipalities for a state"
  task :fetch_mun, [:state] do |_t, args|
    raise "Missing required parameter: state" if args[:state].blank?

    state = args[:state]

    new_municipalities = Scrapers::Municipalities.fetch(state)
    Core::StateManager.update_municipalities(state, new_municipalities)
  end

  def fetch_with_state_source(municipality_context)
    puts "#{municipality_context[:state]} - #{municipality_context[:municipality_entry]["name"]} - Fetching with state source"
    people_config = municipality_context[:config]["people"]
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])

    source_directory_list_config = Scrapers::MunicipalityOfficials.fetch_with_state_level(municipality_context)

    if source_directory_list_config["type"] == "directory_list"
      people = source_directory_list_config["people"]
      people_with_canoncial_names, people_config = Services::Shared::People.collect_people(people_config, [], people)
      formatted_people = Core::PeopleManager.format_people(people_config, people_with_canoncial_names,
                                                           positions_config)
      source_directory_list_config["people"] = formatted_people
    end

    [source_directory_list_config, people_config]
  end

  def fetch_with_scrape(municipality_context)
    request_cache = {}

    # OpenAI - LLM call
    page_fetcher, source_urls, source_dirs, people, people_config = process_with_llm(
      municipality_context, "openai",
      seeded_urls: municipality_context[:config]["scrape_sources"] || [],
      request_cache: request_cache
    )

    municipality_context[:config]["people"] = people_config

    # openai is the only call that scrapes images; arbitrarily choose openai for this
    # since it's the first call
    people_with_images = process_images(municipality_context, source_dirs, people)
    Core::PeopleManager.update_people(municipality_context, people_with_images, "openai.after")

    # Gemini - LLM call
    _, _, _, _, people_config = process_with_llm(municipality_context, "gemini",
                                                 page_fetcher: page_fetcher,
                                                 seeded_urls: source_urls,
                                                 request_cache: request_cache)

    people_config
  end

  def process_with_llm(municipality_context, llm_service_string, page_fetcher: nil,
                       seeded_urls: [], request_cache: {})
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])

    page_fetcher, source_dirs, accumulated_people, people_config = Core::MunicipalScraper.fetch(
      llm_service_string,
      municipality_context,
      page_fetcher: page_fetcher,
      seeded_urls: seeded_urls,
      request_cache: request_cache
    )

    Core::PeopleManager.update_people(municipality_context, accumulated_people, "#{llm_service_string}.before")
    people = Core::PeopleManager.format_people(people_config, accumulated_people, positions_config)
    Core::PeopleManager.update_people(municipality_context, people, "#{llm_service_string}.after")

    source_urls = people.map { |person| person["sources"] }.flatten.uniq

    [page_fetcher, source_urls, source_dirs, people, people_config]
  end

  def aggregate_sources(municipality_context, sources: [])
    state = municipality_context[:state]
    municipality_entry = municipality_context[:municipality_entry]
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])
    people_config = municipality_context[:config]["people"]
    validated_result = Validators::CityPeople.validate_sources(municipality_context)

    combined_people = validated_result[:merged_sources]
    people = Core::PeopleManager.format_people(people_config, combined_people, positions_config)

    Core::PeopleManager.update_people(municipality_context, people)

    officials_hash = Digest::MD5.hexdigest(people.to_yaml)
    Core::StateManager.update_municipalities(state, [
                                               { "gnis" => municipality_entry["gnis"],
                                                 "meta_updated_at" => Time.now
                                                  .in_time_zone("America/Los_Angeles")
                                                  .strftime("%Y-%m-%d"),
                                                 "meta_hash" => officials_hash,
                                                 "meta_sources" => sources }
                                             ])

    people.map { |person| person["sources"] }.flatten.uniq
  end

  def prepare_directories(state, municipality_entry)
    cache_destination_dir = PathHelper.get_city_cache_path(state, municipality_entry["gnis"])

    # Remove cache folder if it exists
    FileUtils.rm_rf(cache_destination_dir) if Dir.exist?(cache_destination_dir)
    FileUtils.mkdir_p(cache_destination_dir)
  end

  def process_images(municipality_context, source_dirs, people)
    state = municipality_context[:state]
    municipality_entry = municipality_context[:municipality_entry]
    puts "Uploading images for #{municipality_entry["name"]}"
    puts "Source dirs: #{source_dirs.inspect}"

    data_city_path = PathHelper.get_data_city_path(state, municipality_entry["gnis"])
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
      next person if person["image"].blank?

      key = File.join(remote_city_path, "images", File.basename(person["image"]))
      person["image"] = Utils::ImageHelper.get_cdn_url(key)

      person
    end
  end

  def self.remove_unused_cache_folders(municipality_context, people)
    gnis = municipality_context[:municipality_entry]["gnis"]
    cache_dir = PathHelper.get_city_cache_path(municipality_context[:state], gnis)
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
