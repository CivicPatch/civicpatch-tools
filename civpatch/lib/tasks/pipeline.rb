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
require_relative "../services/google_sheets"

namespace :pipeline do
  desc "Scrape council members for a specific municipality"
  task :fetch, [:state, :geoid, :create_pr, :send_costs] do |_t, args|
    state = args[:state]
    geoid = args[:geoid]
    create_pr = args[:create_pr].to_s.downcase == "true"
    send_costs = args[:send_costs].to_s.downcase == "true"

    github = Services::GitHub.new
    context = Core::ContextManager.get_context(state, geoid)

    scrape(context)

    Services::GoogleSheets.send_costs if send_costs

    github.update_branch(context)
    github.create_pull_request(context) if create_pr
  end

  desc "Fetch city officials from state source"
  task :fetch_from_state, [:state] do |_t, args|
    # Use with caution, expensive call that should be run
    # only once per initial state setup to scaffold data
    state = args[:state]

    municipalities = Core::StateManager.get_municipalities(state)["municipalities"]
    municipalities.each do |municipality_entry|
      context = Core::ContextManager.get_context(state, municipality_entry["geoid"])
      next unless municipality_entry["website"].present?

      _, people_config = fetch_with_state_source(context)
      aggregate_sources(context, sources: %w[state_source])
      context = Core::ContextManager.update_context_config(context, people: people_config)
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
    Core::PeopleManager.update_people(municipality_context, formatted_people, "#{source_directory_list["type"]}.after")

    [formatted_people, people_config]
  end

  def fetch_with_scrape(municipality_context, people_hint)
    request_cache = {}

    # OpenAI - LLM call
    # This is also the only call that gathers images
    seeded_urls, people_config = process_with_llm(
      municipality_context, "openai",
      seeded_urls: municipality_context[:config]["sources"] || [],
      request_cache: request_cache,
      people_hint: people_hint
    )

    municipality_context[:config]["people"] = people_config

    # Gemini - LLM call
    _, people_config = process_with_llm(municipality_context, "gemini",
                                        seeded_urls: seeded_urls,
                                        request_cache: request_cache,
                                        people_hint: people_hint)

    people_config
  end

  def process_with_llm(municipality_context, llm_service_string,
                       seeded_urls: [], request_cache: {}, people_hint: [])
    positions_config = Core::CityManager.get_config(municipality_context[:government_type])

    accumulated_people, people_config = Core::MunicipalScraper.fetch(
      llm_service_string,
      municipality_context,
      seeded_urls: seeded_urls,
      request_cache: request_cache,
      people_hint: people_hint
    )

    Core::PeopleManager.update_people(municipality_context, accumulated_people, "#{llm_service_string}.before")
    people = Core::PeopleManager.format_people(people_config, accumulated_people, positions_config)
    Core::PeopleManager.update_people(municipality_context, people, "#{llm_service_string}.after")

    source_urls = people.map { |person| person["sources"] }.flatten.uniq

    [source_urls, people_config]
  end

  def aggregate_sources(context, sources: [])
    state = context[:state]
    merged_people = Resolvers::PeopleResolver.merge_people_across_sources(context)

    people = process_images(context, merged_people)

    Core::PeopleManager.update_people(context, people)

    people_hash = Digest::MD5.hexdigest(people.to_yaml)
    Core::StateManager.update_municipalities(state, [
                                               { "geoid" => context["geoid"],
                                                 "meta_updated_at" => Time.now
                                                  .in_time_zone("America/Los_Angeles")
                                                  .strftime("%Y-%m-%d"),
                                                 "meta_hash" => people_hash,
                                                 "meta_sources" => sources }
                                             ])
    people
  end

  def prepare_directories(state, municipality_entry)
    cache_destination_dir = Core::PathHelper.get_city_cache_path(state, municipality_entry["geoid"])

    # Remove cache folder if it exists
    FileUtils.rm_rf(cache_destination_dir) if Dir.exist?(cache_destination_dir)
    FileUtils.mkdir_p(cache_destination_dir)
  end

  def process_images(municipality_context, people)
    state = municipality_context[:state]
    municipality_entry = municipality_context[:municipality_entry]

    city_cache_path = Core::PathHelper.get_city_cache_path(state, municipality_entry["geoid"])
    image_map_path = File.join(city_cache_path, "images", "image_map.json")

    return people unless File.exist?(image_map_path)

    image_map = JSON.parse(File.read(image_map_path))

    data_city_path = Core::PathHelper.get_data_city_path(state, municipality_entry["geoid"])
    # Find last instance of data/ because repo could start with open-data/data/
    remote_city_path = data_city_path.rpartition("data/").last

    source_images_dir = File.join(city_cache_path, "images")

    people.map do |person|
      next person unless person["image"].present?

      image_key = image_map.keys.find { |key| image_map[key] == person["image"] }
      next person unless image_key.present?

      file_path = File.join(source_images_dir, image_key)
      file_key = File.join(remote_city_path, "images", image_key)
      puts "Uploading #{file_path} to remote #{file_key}"
      content_type = Utils::ImageHelper.determine_mime_type(file_path)
      Services::Spaces.put_object(file_key, file_path, content_type)
      person["cdn_image"] = Utils::ImageHelper.get_cdn_url(file_key)

      person
    end
  end

  def self.on_complete(municipality_context)
    geoid = municipality_context[:municipality_entry]["geoid"]
    people = Core::PeopleManager.get_people(municipality_context[:state], geoid)
    state = municipality_context[:state]

    source_urls = people.flat_map do |person|
      person["sources"]
    end.uniq

    Core::CacheManager.clean(state, geoid, source_urls)
    Core::ConfigManager.finalize_config(state, geoid, municipality_context[:config])
  end

  private

  def self.scrape(context)
    state = context[:state]
    municipality_entry = context[:municipality_entry]
    prepare_directories(state, municipality_entry)

    people_hint, people_config = fetch_with_state_source(context)
    context = Core::ContextManager
              .update_context_config(context,
                                     people: people_config)

    people_config = fetch_with_scrape(context, people_hint)
    context = Core::ContextManager
              .update_context_config(context,
                                     people: people_config)

    aggregate_sources(context,
                      sources: %w[state_source gemini openai])

    on_complete(context)
  end
end
