require "utils/url_helper"

module CityScraper
  class PeopleScraper
    def self.fetch(
      llm_service_string,
      state,
      gnis,
      config,
      search_engines = %w[manual brave],
      seeded_urls = []
    )
      puts "Fetching with #{llm_service_string}"
      data_fetcher = Scrapers::DataFetcher.new
      city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
      city_cache_path = PathHelper.get_city_cache_path(state, gnis)

      processed_search_urls = []
      page_content_cache_dirs = []
      officials_from_search = []

      search_engines.each do |engine|
        search_result_urls = Core::SearchRouter.fetch_search_results(engine, state, city_entry, seeded_urls)
        urls_to_scrape = search_result_urls - processed_search_urls
        puts "#{llm_service_string} Engine #{engine} found #{search_result_urls.count} search results for #{city_entry["name"]}"
        puts "#{llm_service_string} URLs to scrape: #{urls_to_scrape.count}"

        new_page_content_cache_dirs, people_from_engine_results = fetch_people(
          llm_service_string,
          state,
          city_entry,
          data_fetcher,
          city_cache_path,
          urls_to_scrape,
          config
        )
        officials_from_search = Core::PeopleManager.merge_people(officials_from_search, people_from_engine_results)

        processed_search_urls += urls_to_scrape
        page_content_cache_dirs += new_page_content_cache_dirs

        is_valid_city_people = Core::PeopleManager.valid_city_people?(officials_from_search)
        break if is_valid_city_people
      end

      officials_with_profile_data = officials_from_search.map do |person|
        website = person["website"]
        next person if website.blank?
        next person if person["sources"].any? { |source| source == website }

        profile_scrape_cache_path = File.join(city_cache_path, Utils::UrlHelper.url_to_safe_folder_name(website))
        profile_content_cache_dir, merged_person_data = scrape_person_website(
          llm_service_string,
          state,
          city_entry,
          data_fetcher,
          profile_scrape_cache_path,
          person
        )
        page_content_cache_dirs << profile_content_cache_dir if profile_content_cache_dir.present?

        merged_person_data
      end

      [page_content_cache_dirs.uniq, officials_with_profile_data]
    end

    def self.scrape_person_website(llm_service_string, state, city_entry, data_fetcher, person_profile_cache_path,
                                   person)
      website = person["website"]
      return [nil, person] if website.blank?

      FileUtils.mkdir_p(person_profile_cache_path)

      content_file = data_fetcher.extract_content(website, person_profile_cache_path)
      return [nil, person] unless content_file

      llm_service = get_llm_service(llm_service_string)
      llm_extracted_profile_data = llm_service.extract_person_information(state, city_entry, person, content_file,
                                                                          website)

      unless llm_extracted_profile_data.present? && llm_extracted_profile_data.is_a?(Hash)
        return [person_profile_cache_path, person]
      end

      merged_data_from_profile = Core::PeopleManager.merge_person(person, llm_extracted_profile_data)

      [person_profile_cache_path, merged_data_from_profile]
    end

    def self.fetch_people(
      llm_service_string,
      state,
      city_entry,
      data_fetcher,
      search_results_base_cache_path,
      urls_from_search,
      config
    )
      cache_dirs_with_results = []
      accumulated_officials = []

      urls_from_search.each do |url|
        cache_name = Utils::UrlHelper.url_to_safe_folder_name(url)
        url_content_cache_path = File.join(search_results_base_cache_path, cache_name)
        FileUtils.mkdir_p(url_content_cache_path)

        officials_from_page = fetch_and_process_page(llm_service_string, state, city_entry, data_fetcher,
                                                     url_content_cache_path, url)

        next unless valid_potential_officials_list?(officials_from_page)

        puts "#{llm_service_string}: Found #{officials_from_page.count} potential officials from #{url}; Positions: #{officials_from_page.map do |p|
          p["positions"]
        end.inspect}"

        cache_dirs_with_results << url_content_cache_path
        accumulated_officials = Core::PeopleManager.merge_people(accumulated_officials, officials_from_page)
        accumulated_officials = Core::PeopleManager.normalize_people(accumulated_officials, config)

        council_members = Core::PeopleManager.get_council_members_count(accumulated_officials)
        mayors = Core::PeopleManager.get_mayors_count(accumulated_officials)

        puts "#{llm_service_string}: Accumulated totals -> Council members: #{council_members}, Mayors: #{mayors}"

        break if Core::PeopleManager.valid_city_people?(accumulated_officials)
      end

      [cache_dirs_with_results, accumulated_officials]
    end

    def self.fetch_and_process_page(llm_service_string, state, city_entry, data_fetcher, url_content_cache_path, url)
      puts "Fetching #{url} for city people extraction"
      content_file = data_fetcher.extract_content(url, url_content_cache_path)
      return [] unless content_file

      llm_service = get_llm_service(llm_service_string)
      llm_service.extract_city_people(state, city_entry, content_file, url)
    end

    def self.valid_potential_officials_list?(potential_officials_list)
      potential_officials_list.present? &&
        potential_officials_list.is_a?(Array) &&
        potential_officials_list.any?
    end

    def self.get_llm_service(llm_service_string)
      case llm_service_string
      when "gpt"
        Services::Openai.new
      when "google_gemini"
        Services::GoogleGemini.new
      end
    end
  end
end
