# frozen_string_literal: true

require_relative "../services/brave"
require_relative "../services/openai"
require_relative "../core/municipal_scraper"
require_relative "../core/page_fetcher"
require_relative "../core/state_manager"
require_relative "../core/search_router"
require_relative "../core/people_manager"
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

    puts cities.map { |c| { "name": c["name"], "gnis": c["gnis"], "county": c["counties"].first } }.to_json
  end

  desc "Scrape city info for a specific city"
  task :fetch, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    municipality_entry = Core::StateManager.get_city_entry_by_gnis(state, gnis)
    municipality_context = {
      state: state,
      municipality_entry: municipality_entry,
      government_type: Scrapers::Municipalities.get_government_type(state, municipality_entry)
    }

    prepare_directories(state, municipality_entry)

    state_source_people = fetch_with_state_source(municipality_context) # State-level city directory source
    # TODO: require all municipalities to have a mayor until we discover otherwise

    # Sometimes state source can lag behind the city source
    #  -- there may be more members listed than are
    # available on the city website
    scrape_exit_config = { people_count: state_source_people.count - 2, key_position: "mayor" }

    fetch_with_scrape(municipality_context, scrape_exit_config)

    aggregate_sources(municipality_context, sources: %w[state_source gemini openai])
    ## Create config.yml for the city
    create_config_yml(state, municipality_entry)

    people = Core::PeopleManager.get_people(state, gnis)
    # remove_unused_cache_folders(state, municipality_entry, people)
  end

  desc "Fetch city officials from state source"
  task :fetch_from_state, [:state] do |_t, args|
    state = args[:state]

    municipalities = Core::StateManager.get_municipalities(state)["municipalities"]
    municipalities.each do |municipality_entry|
      municipality_context = {
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
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])
    data_source_dir = PathHelper.get_data_source_city_path(municipality_context[:state],
                                                           municipality_context[:municipality_entry]["gnis"])

    # This call can fail if the state source is down (e.g. MRSC.org for WA)
    begin
      people = Scrapers::MunicipalityOfficials.fetch_with_state_level(municipality_context)
      FileUtils.mkdir_p(data_source_dir) unless Dir.exist?(data_source_dir)
      Core::PeopleManager.update_people(municipality_context[:state], municipality_context[:municipality_entry],
                                        people, "state_source.before")
      formatted_people = Core::PeopleManager.format_people(people, positions_config)
      Core::PeopleManager.update_people(municipality_context[:state], municipality_context[:municipality_entry],
                                        formatted_people, "state_source.after")

      formatted_people
    rescue StandardError => e
      puts "Error pulling from state source: #{e}"
      puts "Backtrace: #{e.backtrace}"
    end
  end

  def fetch_with_scrape(municipality_context, scrape_exit_config)
    request_cache = {}
    state = municipality_context[:state]
    municipality_entry = municipality_context[:municipality_entry]
    config_file_path = PathHelper.get_municipality_config_path(state, municipality_entry["gnis"])
    config = { "scrape_sources" => [] }
    config = YAML.load_file(config_file_path) if File.exist?(config_file_path)
    config_urls = config["scrape_sources"] ||= []

    # OpenAI - LLM call
    page_fetcher, source_urls, source_dirs, people = process_with_llm(
      municipality_context, "openai",
      scrape_exit_config: scrape_exit_config,
      seeded_urls: config_urls,
      request_cache: request_cache
    )

    # openai is the only call that scrapes images; arbitrarily choose openai for this
    # since it's the first call
    people_with_images = process_images(municipality_context, source_dirs, people)
    Core::PeopleManager.update_people(state, municipality_entry, people_with_images, "openai.after")

    # Gemini - LLM call
    process_with_llm(municipality_context, "gemini",
                     scrape_exit_config: scrape_exit_config,
                     page_fetcher: page_fetcher,
                     seeded_urls: source_urls,
                     request_cache: request_cache)
  end

  def process_with_llm(municipality_context, llm_service_string, page_fetcher: nil, scrape_exit_config: [],
                       seeded_urls: [], request_cache: {})
    state = municipality_context[:state]
    municipality_entry = municipality_context[:municipality_entry]
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])

    page_fetcher, source_dirs, accumulated_people = Core::MunicipalScraper.fetch(
      llm_service_string,
      municipality_context,
      page_fetcher: page_fetcher,
      scrape_exit_config: scrape_exit_config,
      seeded_urls: seeded_urls,
      request_cache: request_cache
    )

    Core::PeopleManager.update_people(state, municipality_entry, accumulated_people, "#{llm_service_string}.before")
    people = Core::PeopleManager.format_people(accumulated_people, positions_config)
    Core::PeopleManager.update_people(state, municipality_entry, people, "#{llm_service_string}.after")

    source_urls = people.map { |person| person["sources"] }.flatten.uniq

    [page_fetcher, source_urls, source_dirs, people]
  end

  def aggregate_sources(municipality_context, sources: [])
    state = municipality_context[:state]
    municipality_entry = municipality_context[:municipality_entry]
    positions_config = Core::CityManager.get_positions(municipality_context[:government_type])
    validated_result = Validators::CityPeople.validate_sources(state, municipality_entry["gnis"])

    combined_people = validated_result[:merged_sources]
    formatted_people = Core::PeopleManager.format_people(combined_people, positions_config)

    Core::PeopleManager.update_people(state, municipality_entry, formatted_people)

    officials_hash = Digest::MD5.hexdigest(combined_people.to_yaml)
    Core::StateManager.update_municipalities(state, [
                                               { "gnis" => municipality_entry["gnis"],
                                                 "meta_updated_at" => Time.now
                                                  .in_time_zone("America/Los_Angeles")
                                                  .strftime("%Y-%m-%d"),
                                                 "meta_hash" => officials_hash,
                                                 "meta_sources" => sources }
                                             ])
  end

  def create_config_yml(state, municipality_entry)
    gnis = municipality_entry["gnis"]
    people = Core::PeopleManager.get_people(state, gnis)
    config_yml = {
      "scrape_sources" => people.map { |person| person["sources"] }.flatten.uniq
    }

    config_path = File.join(PathHelper.get_data_source_city_path(state, municipality_entry["gnis"]), "config.yml")
    File.write(config_path, config_yml.to_yaml)
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
      next if person["image"].blank?

      key = File.join(remote_city_path, "images", File.basename(person["image"]))
      person["image"] = Utils::ImageHelper.get_cdn_url(key)

      person
    end
  end

  def self.remove_unused_cache_folders(state, municipality_entry, people)
    gnis = municipality_entry["gnis"]
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
