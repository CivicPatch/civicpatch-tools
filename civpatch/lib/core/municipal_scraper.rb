# frozen_string_literal: true

require "utils/url_helper"
require "services/shared/people"
require "services/google_gemini"
require "services/openai"
require "resolvers/search_resolver"
require "core/crawler"

module Core
  class MunicipalScraper
    MAX_URLS_TO_SCRAPE = 20
    MIN_PEOPLE_TO_FIND = 5

    def self.fetch( # rubocop:disable Metrics/AbcSize,Metrics/CyclomaticComplexity,Metrics/MethodLength,Metrics/PerceivedComplexity
      llm_service_string,
      municipality_context,
      request_cache: {},
      # page_fetcher: nil,
      people_hint: [],
      seeded_urls: [] # Urls to scrape first
    )
      puts "Fetching with #{llm_service_string}"
      # page_fetcher ||= Core::PageFetcher.new
      municipality_entry = municipality_context[:municipality_entry]
      state = municipality_context[:state]
      geoid = municipality_entry["geoid"]
      city_cache_path = Core::PathHelper.get_city_cache_path(state, geoid)
      keyword_groups = Core::CityManager.get_search_keywords_as_array(municipality_context[:government_type])

      puts "#{llm_service_string}: Looking for #{municipality_context[:config]["scrape_exit_config"]}"

      context = {
        seeded_urls: seeded_urls,
        llm_service_string: llm_service_string,
        municipality_context: municipality_context,
        # page_fetcher: page_fetcher,
        city_cache_path: city_cache_path,
        request_cache: request_cache,
        people_hint: people_hint
      }

      # Initialize combined data hash
      data = { accumulated_people: [], processed_urls: [],
               people_config: municipality_context[:config]["people"] }
      exit_early = false

      avoid_keywords = %w[alerts news event calendar archive]

      %w[seeded search crawler].each do |scrape_with|
        break unless should_continue_scraping?(context, data)

        puts "Scraping with #{scrape_with}"

        case scrape_with
        when "seeded"
          exit_early = false
          next if seeded_urls.blank?

          puts "#{llm_service_string}: Scraping with seeded URLs"

          urls = seeded_urls
        when "search"
          exit_early = true
          keyword_terms = keyword_groups.map { |group| group[:name] }
          puts "#{llm_service_string}: Scraping with search with keyword_terms: #{keyword_terms}"
          urls = scrape_with_search(context, keyword_terms)
          puts "Search results: #{urls}"
        when "crawler"
          exit_early = true
          puts "#{llm_service_string}: Scraping with crawler #{keyword_groups}, avoid keywords #{avoid_keywords}"
          urls = scrape_with_crawler(context, keyword_groups, avoid_keywords)
        end

        next if urls.blank?

        urls = urls.map { |url| Utils::UrlHelper.format_url(url) }.reject do |url|
          avoid_keywords.any? { |keyword| url.include?(keyword) }
        end

        puts "#{llm_service_string}: URLs to scrape:"
        puts urls.join("\n")

        data = scrape_urls(context, data, urls_to_process: urls, early_exit: exit_early)
      end

      accumulated_people = scrape_profiles(context, data[:accumulated_people],
                                           data[:processed_urls])

      Core::PeopleManager.update_people(municipality_context, accumulated_people,
                                        "#{llm_service_string}-scrape-collected.before")

      formatted_officials = accumulated_people.map do |official|
        Services::Shared::People.format_person(official)
      end.compact

      [formatted_officials, data[:people_config]]
    end

    def self.scrape_with_search(context, keyword_terms)
      return context[:request_cache]["search"] if context[:request_cache]["search"].present?

      results = Resolvers::SearchResolver.municipal_search(context[:municipality_context],
                                                           keyword_terms)
      context[:request_cache]["search"] = results
      results
    end

    def self.scrape_with_crawler(context, keyword_groups, avoid_keywords)
      return context[:request_cache]["crawler"] if context[:request_cache]["crawler"].present?

      results = Core::Crawler.crawl(context[:municipality_context][:municipality_entry]["website"],
                                    keyword_groups: keyword_groups,
                                    avoid_keywords: avoid_keywords)
      context[:request_cache]["crawler"] = results
      results
    end

    def self.scrape_urls(
      context,
      data,
      urls_to_process: [],
      early_exit: false
    )
      return data if urls_to_process.blank?

      accumulated_people = data[:accumulated_people] || []
      processed_urls = data[:processed_urls] || []
      people_config = data[:people_config]
      urls_to_process = urls_to_process.reject do |url|
        processed_urls.include?(url)
      end

      urls_to_process.each do |url|
        break if early_exit && !should_continue_scraping?(context, data)

        people = scrape_url_for_municipal_directory(context, url, context[:people_hint])

        unless people.blank?
          accumulated_people, people_config = Services::Shared::People.collect_people(people_config,
                                                                                      accumulated_people, people)
          data[:accumulated_people] = accumulated_people
          data[:people_config] = people_config
        end

        processed_urls << url
        data[:processed_urls] = processed_urls

        found_people = accumulated_people.map { |person| "#{person["name"]} (#{person["positions"].first})" }
        # num_urls_scraped = processed_urls.count
        # puts "#{context[:llm_service_string]}: Scraping #{url}: #{num_urls_scraped} of MAX (#{MAX_URLS_TO_SCRAPE})"
        puts "#{context[:llm_service_string]}: #{found_people.count} people found: #{found_people}"
      end

      data
    end

    def self.scrape_profiles(context, accumulated_people, processed_urls)
      profile_processed_urls = processed_urls.dup
      people_config = context[:municipality_context][:config]["people"]

      accumulated_people.map do |person|
        next person if Services::Shared::People.all_contact_data_points_present?(person) && person["image"].present?
        next person if person["websites"].blank?

        unique_websites = person["websites"].map { |website| website["data"] }.uniq
        puts "Websites found for #{person["name"]}: #{unique_websites}"

        unique_websites.each do |original_url|
          next if original_url.blank?
          next if profile_processed_urls.include?(original_url)

          puts "Fetching from #{original_url} for #{person["name"]}"
          profile_processed_urls << original_url
          people = scrape_url_for_municipal_directory(
            context,
            original_url,
            [],
            person["name"]
          )

          next if people.blank?

          person_with_website_data = Resolvers::PersonResolver.find_by_name(people_config, people, person["name"])

          next if person_with_website_data.blank?

          person = Services::Shared::People.merge_person(person, person_with_website_data)
        end

        person
      end
    end

    def self.scrape_url_for_municipal_directory(context, url, people_hint = [], person_name = "")
      llm_service_string = context[:llm_service_string]
      # page_fetcher = context[:page_fetcher]
      cache_path = context[:city_cache_path]
      municipality_context = context[:municipality_context]
      llm_service = get_llm_service(llm_service_string)

      if person_name.present?
        puts "Scraping #{url} for #{person_name}"
      else
        puts "Scraping #{url} for people (#{people_hint.count})"
      end

      url_content_path = File.join(cache_path, Utils::UrlHelper.url_to_safe_folder_name(url))
      FileUtils.mkdir_p(url_content_path)

      content_file = Core::PageFetcher.extract_content(url, url_content_path)
      return nil unless content_file.present?

      people = llm_service.extract_city_people(municipality_context, content_file, url, people_hint, person_name)

      return nil unless people.present? && people.is_a?(Array) && people.count.positive?

      people
    end

    def self.get_llm_service(llm_service_string)
      case llm_service_string
      when "openai"
        Services::Openai.new
      when "gemini"
        Services::GoogleGemini.new
      end
    end

    def self.should_continue_scraping?(context, data)
      accumulated_officials = data[:accumulated_people]
      num_urls_scraped = data[:processed_urls].count

      num_seeded_urls = context[:seeded_urls].present? ? context[:seeded_urls].count : 0
      return false if num_urls_scraped >= [MAX_URLS_TO_SCRAPE, num_seeded_urls].max

      valid_officials_count = accumulated_officials.count do |official|
        # TODO: should only check if the positions are relevant
        official["positions"].present? && Services::Shared::People.profile_data_points_present?(official)
      end

      num_people_hint = context[:people_hint].present? ? context[:people_hint].count : 0
      people_to_find = [num_people_hint - 2, MIN_PEOPLE_TO_FIND].max
      return true if valid_officials_count < people_to_find

      false
    end
  end
end
