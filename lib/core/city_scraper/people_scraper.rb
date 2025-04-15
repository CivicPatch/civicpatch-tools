require "utils/url_helper"
require "services/shared/people"

module CityScraper
  class PeopleScraper
    @@MAX_URLS_TO_SCRAPE = 20

    def self.fetch(
      llm_service_string,
      state,
      gnis,
      government_type,
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
        break unless should_continue_scraping?(officials_from_search, page_content_cache_dirs.count)

        search_result_urls = Core::SearchRouter.fetch_search_results(engine, state, city_entry, government_type,
                                                                     seeded_urls)
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
          officials_from_search
        )
        officials_from_search = Services::Shared::People.collect_people(officials_from_search,
                                                                        people_from_engine_results)

        processed_search_urls += urls_to_scrape
        page_content_cache_dirs += new_page_content_cache_dirs
      end

      officials_with_profile_data = officials_from_search.map do |person|
        next person if Services::Shared::People.all_contact_data_points_present?(person)
        next person if person["websites"].blank?

        person["websites"].each do |website|
          next if website["data"].blank?

          cache_key = Utils::UrlHelper.url_to_safe_folder_name(website["data"])
          next if page_content_cache_dirs.include?(File.join(city_cache_path, cache_key))

          site_cache_dir = File.join(city_cache_path, cache_key)

          person_data = scrape_person_website(
            llm_service_string,
            state,
            city_entry,
            data_fetcher,
            site_cache_dir,
            person,
            website["data"]
          )

          next if person_data.blank?

          page_content_cache_dirs << site_cache_dir
          person = Services::Shared::People.merge_person(person, person_data)
        end

        person
      end

      Core::PeopleManager.update_people(state, city_entry, officials_with_profile_data,
                                        "scrape-collected.before")

      formatted_officials = officials_from_search.map do |official|
        Services::Shared::People.format_person(official)
      end

      [page_content_cache_dirs.uniq, formatted_officials]
    end

    def self.scrape_person_website(
      llm_service_string,
      state,
      city_entry,
      data_fetcher,
      cache_path,
      person,
      website
    )
      puts "Scraping for #{person["name"]} from #{website}"
      FileUtils.mkdir_p(cache_path)

      content_file = data_fetcher.extract_content(website, cache_path)
      return [nil, person] unless content_file

      llm_service = get_llm_service(llm_service_string)
      llm_extracted_profile_data = llm_service.extract_person_information(state, 
        city_entry, person, content_file,
                                                                          website)

      return person unless llm_extracted_profile_data.present? && llm_extracted_profile_data.is_a?(Hash)

      llm_extracted_profile_data
    end

    def self.fetch_people(
      llm_service_string,
      state,
      city_entry,
      data_fetcher,
      search_results_base_cache_path,
      urls_from_search,
      accumulated_officials
    )
      cache_dirs_with_results = []

      urls_from_search.each do |url|
        cache_name = Utils::UrlHelper.url_to_safe_folder_name(url)
        url_content_cache_path = File.join(search_results_base_cache_path, cache_name)
        FileUtils.mkdir_p(url_content_cache_path)

        process_page_start = Time.now
        officials_from_page = fetch_and_process_page(llm_service_string, state, city_entry, data_fetcher,
                                                     url_content_cache_path, url)
        process_page_end = Time.now
        puts "Process page took #{process_page_end - process_page_start} seconds"

        next unless valid_potential_officials_list?(officials_from_page)

        puts "#{llm_service_string}: Found #{officials_from_page.count} potential officials from #{url}; Positions: #{officials_from_page.map do |p|
          p["positions"]
        end.inspect}"

        cache_dirs_with_results << url_content_cache_path
        collect_people_start = Time.now
        accumulated_officials = Services::Shared::People.collect_people(accumulated_officials, officials_from_page)
        collect_people_end = Time.now
        puts "Collect people took #{collect_people_end - collect_people_start} seconds"

        break unless should_continue_scraping?(accumulated_officials, cache_dirs_with_results.count)
      end

      [cache_dirs_with_results, accumulated_officials]
    end

    def self.fetch_and_process_page(
      llm_service_string,
      state,
      city_entry,
      data_fetcher,
      url_content_cache_path,
      url)
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

    def self.should_continue_scraping?(accumulated_officials, num_urls_scraped)
      return false if num_urls_scraped >= @@MAX_URLS_TO_SCRAPE

      member_count = accumulated_officials.count do |person|
        person["positions"].present? &&
          person["positions"].any? { |position| position.downcase.include?("member") } &&
          Services::Shared::People.profile_data_points_present?(person)
      end

      leader_count = accumulated_officials.count do |person|
        person["positions"].present? &&
          person["positions"].any? { |position| position.downcase.include?("mayor") } &&
          Services::Shared::People.profile_data_points_present?(person)
      end

      return false if leader_count >= 1 && member_count >= 4

      true
    end
  end
end
