require "utils/url_helper"

module CityScraper
  class PeopleScraper
    # def initialize(state, engine, openai_service, data_fetcher, city_entry, city_directory)
    #  @state = state
    #  @engine = engine
    #  @openai_service = openai_service
    #  @data_fetcher = data_fetcher
    #  @city_entry = city_entry
    #  @city_directory = city_directory
    # end

    def self.fetch(
      llm_service,
      state,
      gnis,
      config,
      search_engines = %w[manual brave],
      seeded_urls = []
    )
      puts "Fetching people with search engines: #{search_engines.join(", ")}"
      # openai_service = Services::Openai.new
      data_fetcher = Scrapers::DataFetcher.new
      city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
      city_path = CityScrape::CityManager.get_city_path(state, city_entry)
      cache_path = File.join(city_path, "cache")

      search_results_processed = []
      local_source_dirs = []
      city_people = []

      search_engines.each do |engine|
        search_result_urls = Core::SearchRouter.fetch_search_results(engine, state, city_entry, seeded_urls)
        search_results_to_process = search_result_urls - search_results_processed
        puts "Engine #{engine} found #{search_result_urls.count} search results for #{city_entry["name"]}"
        puts "Search results to process: #{search_results_to_process.count}"
        puts search_results_to_process.join("\n")

        new_source_dirs, found_people = fetch_people(llm_service, state, city_entry, data_fetcher, cache_path,
                                                     search_results_to_process, config)
        city_people = Core::PeopleManager.merge_people(city_people, found_people)

        search_results_processed += search_results_to_process
        local_source_dirs += new_source_dirs

        break if Core::PeopleManager.valid_city_people?(city_people)
      end

      people = city_people.map do |person|
        website = person["website"]
        next person if website.blank?
        next person if person["sources"].any? { |source| source == website }

        person_cache_path = File.join(cache_path, Utils::UrlHelper.url_to_safe_folder_name(website))
        person_dir, updated_person = scrape_person_website(llm_service,
                                                           state,
                                                           city_entry,
                                                           data_fetcher,
                                                           person_cache_path,
                                                           person)
        updated_person = Core::PeopleManager.merge_person(person, updated_person)
        next person unless updated_person.present?

        local_source_dirs << person_dir if person_dir.present?

        updated_person
      end

      [local_source_dirs, people]
    end

    def self.scrape_person_website(llm_service, state, city_entry, data_fetcher, cache_path, person)
      website = person["website"]
      return nil if website.blank?

      return nil if person["sources"].any? do |source|
        Utils::UrlHelper.same_url?(source, website)
      end

      puts "Scraping for person: #{person["name"]} at url: #{website}"

      person_name = Zaru.sanitize!(person["name"].gsub(/\s+/, "_"))

      person_dir = File.join(cache_path, person_name.to_s)
      FileUtils.mkdir_p(person_dir)

      content_file = data_fetcher.extract_content(website, person_dir)
      person_info = llm_service.extract_person_information(state, city_entry, person, content_file, website)

      return nil unless person_info.present? && person_info.is_a?(Hash)

      updated_person = Core::PeopleManager.merge_person(person, person_info)

      [person_dir, updated_person]
    end

    def self.fetch_people(
      llm_service,
      state,
      city_entry,
      data_fetcher,
      cache_path,
      search_results,
      config
    )
      directories_with_people = []
      found_people = []

      search_results.each do |url|
        cache_name = Utils::UrlHelper.url_to_safe_folder_name(url)
        page_cache_path = File.join(cache_path, cache_name)
        FileUtils.mkdir_p(page_cache_path)

        partial_people = fetch_and_process_page(llm_service, state, city_entry, data_fetcher, page_cache_path, url)

        next unless valid_partial_directory?(partial_people)

        puts "Found partial set of people: #{partial_people.count}; #{partial_people.map { |p| p["positions"] }}"

        directories_with_people << page_cache_path
        found_people = Core::PeopleManager.merge_people(found_people, partial_people)
        found_people = Core::PeopleManager.normalize_people(found_people, config)

        council_members = Core::PeopleManager.get_council_members_count(found_people)
        mayors = Core::PeopleManager.get_mayors_count(found_people)

        puts "Processed url: #{url} -> Council members: #{council_members}, Mayors: #{mayors}"
        break if Core::PeopleManager.valid_city_people?(found_people)
      end

      [directories_with_people, found_people]
    end

    def self.fetch_and_process_page(llm_service, state, city_entry, data_fetcher, page_cache_path, url)
      puts "Fetching #{url}"
      content_file = data_fetcher.extract_content(url, page_cache_path)
      llm_service.extract_city_people(state, city_entry, content_file, url)
    end

    def self.valid_partial_directory?(partial_directory)
      partial_directory.present? && partial_directory.any?
    end
  end
end
