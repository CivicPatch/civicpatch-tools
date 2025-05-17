# frozen_string_literal: true

require_relative "../services/brave"
require_relative "../services/openai"
require_relative "../core/context_manager"
require_relative "../core/config_manager"
require_relative "../core/municipal_scraper"
require_relative "../core/page_fetcher"
require_relative "../core/cache_manager"
require_relative "../core/state_manager"
require_relative "../core/people_manager"
require_relative "../resolvers/person_resolver"
require_relative "../services/spaces"
require_relative "../scrapers/municipalities"
require_relative "../scrapers/municipality_officials"
require_relative "../services/github"

namespace :pipeline do
  task :hello do
    puts "Hello, world!"
  end

  desc "Scrape council members for a specific municipality"
  task :fetch, [:state, :gnis, :create_pr] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]
    create_pr = args[:create_pr].to_s.downcase == "true"

    github = Services::GitHub.new
    context = Core::ContextManager.get_context(state, gnis)

    scrape(context)

    github.create_pull_request(context) if create_pr
  end

  desc "Fetch city officials from state source"
  task :fetch_from_state, [:state] do |_t, args|
    # Use with caution, expensive call that should be run
    # only once per initial state setup to scaffold data
    state = args[:state]

    municipalities = Core::StateManager.get_municipalities(state)["municipalities"]
    municipalities.each do |municipality_entry|
      context = Core::ContextManager.get_context(state, municipality_entry["gnis"])
      next unless municipality_entry["website"].present?
      next unless context[:config]["source_directory_list"]["type"] == "directory_list_default"

      source_directory_list, people_config = fetch_with_state_source(context)
      aggregate_sources(context, sources: %w[state_source])
      context = Core::ContextManager.update_context_config(context,
                                                           source_directory_list: source_directory_list,
                                                           people: people_config)
      finalize(context)
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
    state = municipality_context[:state]
    municipality_name = municipality_context[:municipality_entry]["name"]
    puts "#{state} - #{municipality_name} - Fetching with state source"
    people_config = municipality_context[:config]["people"]
    positions_config = Core::CityManager.get_config(municipality_context[:government_type])

    source_directory_list = Scrapers::MunicipalityOfficials.fetch_with_state_level(municipality_context)

    people = source_directory_list["people"]
    people_with_canoncial_names, people_config = Services::Shared::People.collect_people(people_config, [], people)
    formatted_people = Core::PeopleManager.format_people(people_config, people_with_canoncial_names,
                                                         positions_config)
    source_directory_list["people"] = formatted_people

    [source_directory_list, people_config]
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
    # people_with_images = process_images(municipality_context, source_dirs, people)
    # Core::PeopleManager.update_people(municipality_context, people_with_images, "openai.after")

    # Gemini - LLM call
    _, _, _, _, people_config = process_with_llm(municipality_context, "gemini",
                                                 page_fetcher: page_fetcher,
                                                 seeded_urls: source_urls,
                                                 request_cache: request_cache)

    people_config
  end

  def process_with_llm(municipality_context, llm_service_string, page_fetcher: nil,
                       seeded_urls: [], request_cache: {})
    positions_config = Core::CityManager.get_config(municipality_context[:government_type])

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
    positions_config = Core::CityManager.get_config(municipality_context[:government_type])
    people_config = municipality_context[:config]["people"]
    validated_result = Resolvers::PeopleResolver.resolve(municipality_context)

    people = Core::PeopleManager.format_people(people_config, validated_result[:merged_sources], positions_config)

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
  end

  def prepare_directories(state, municipality_entry)
    cache_destination_dir = Core::PathHelper.get_city_cache_path(state, municipality_entry["gnis"])

    # Remove cache folder if it exists
    FileUtils.rm_rf(cache_destination_dir) if Dir.exist?(cache_destination_dir)
    FileUtils.mkdir_p(cache_destination_dir)
  end

  def process_images(municipality_context, source_dirs, people)
    state = municipality_context[:state]
    municipality_entry = municipality_context[:municipality_entry]
    puts "Uploading images for #{municipality_entry["name"]}"
    puts "Source dirs: #{source_dirs.inspect}"

    data_city_path = Core::PathHelper.get_data_city_path(state, municipality_entry["gnis"])
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

  def self.on_complete(municipality_context)
    gnis = municipality_context[:municipality_entry]["gnis"]
    people = Core::PeopleManager.get_people(municipality_context[:state], gnis)
    state = municipality_context[:state]

    source_urls = people.flat_map do |person|
      person["sources"]
    end.uniq

    Core::ContextManager
      .update_context_config(municipality_context,
                             scrape_sources: source_urls)

    Core::CacheManager.clean(state, gnis, source_urls)
    Core::ConfigManager.finalize_config(state, gnis, municipality_context[:config])
  end

  private

  def self.scrape(context)
    state = context[:state]
    municipality_entry = context[:municipality_entry]
    prepare_directories(state, municipality_entry)

    source_directory_list_config, people_config = fetch_with_state_source(context)
    context = Core::ContextManager
              .update_context_config(context,
                                     source_directory_list: source_directory_list_config,
                                     people: people_config)

    people_config = fetch_with_scrape(context)
    context = Core::ContextManager
              .update_context_config(context,
                                     people: people_config)

    aggregate_sources(context,
                      sources: %w[state_source gemini openai])

    on_complete(context)
  end
end
