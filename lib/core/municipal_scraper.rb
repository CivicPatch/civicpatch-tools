require "utils/url_helper"
require "services/shared/people"
require "set"

module Core
  class MunicipalScraper
    @@MAX_URLS_TO_SCRAPE = 20

    def self.fetch(
      llm_service_string,
      municipality_context,
      search_engines: %w[manual brave],
      page_fetcher: nil,
      cached_urls: []
    )
      puts "Fetching with #{llm_service_string}"
      page_fetcher ||= Core::PageFetcher.new
      city_entry = municipality_context[:city_entry]
      state = municipality_context[:state]
      gnis = municipality_context[:city_entry]["gnis"]
      city_cache_path = PathHelper.get_city_cache_path(state, gnis)

      context = {
        llm_service_string: llm_service_string,
        state: municipality_context[:state],
        city_entry: municipality_context[:city_entry],
        gnis: municipality_context[:city_entry]["gnis"],
        government_type: municipality_context[:government_type],
        page_fetcher: page_fetcher,
        city_cache_path: city_cache_path
      }

      data = if cached_urls.present? && cached_urls.count.positive?
               scrape_city_directory_urls(context, urls_to_process: cached_urls)
             else
               scrape_from_search_engines(context, [], [], search_engines: search_engines)
             end

      profile_content_dirs, accumulated_people = scrape_profiles(context, data[:accumulated_people],
                                                                 data[:content_dirs])

      Core::PeopleManager.update_people(state, city_entry, accumulated_people,
                                        "#{llm_service_string}-scrape-collected.before")

      formatted_officials = accumulated_people.map do |official|
        Services::Shared::People.format_person(official)
      end.compact

      content_dirs = data[:content_dirs] + profile_content_dirs

      [page_fetcher, content_dirs, formatted_officials]
    end

    def self.scrape_city_directory_urls(
      context,
      urls_to_process: [],
      processed_urls: [],
      accumulated_people: [],
      early_exit: false
    )
      content_dirs = []

      urls_to_process.each do |url|
        break if early_exit && !should_continue_scraping?(accumulated_people, processed_urls.count)

        puts "Fetching from URL: #{url}"
        url_content_path, people = scrape_url_for_municipal_directory(context, url)
        next if people.blank?

        processed_urls << url
        content_dirs << url_content_path
        accumulated_people = Services::Shared::People.collect_people(accumulated_people, people)
      end

      {
        accumulated_people: accumulated_people,
        content_dirs: content_dirs,
        processed_urls: processed_urls
      }
    end

    def self.scrape_from_search_engines(
      context,
      accumulated_people = [],
      processed_urls = [],
      search_engines: %w[manual brave]
    )
      state = context[:state]
      city_entry = context[:city_entry]
      government_type = context[:government_type]

      content_dirs = []

      search_engines.each do |engine|
        break unless should_continue_scraping?(accumulated_people, content_dirs.count)

        search_result_urls = Core::SearchRouter.fetch_search_results(
          engine,
          state,
          city_entry,
          government_type
        )
        urls_to_scrape = search_result_urls - processed_urls

        puts "#{context[:llm_service_string]} Search result urls: #{search_result_urls}"
        puts "#{context[:llm_service_string]} Urls already scraped: #{processed_urls}"
        puts "#{context[:llm_service_string]} Engine #{engine} found #{search_result_urls.count} search results for #{city_entry["name"]}"
        puts "#{context[:llm_service_string]} URLs to scrape: #{urls_to_scrape.count}"

        data_from_scraped_urls = scrape_city_directory_urls(
          context,
          urls_to_process: urls_to_scrape,
          processed_urls: processed_urls,
          accumulated_people: accumulated_people,
          early_exit: true
        )

        accumulated_people = data_from_scraped_urls[:accumulated_people]
        processed_urls += data_from_scraped_urls[:processed_urls]
        content_dirs += data_from_scraped_urls[:content_dirs]
      end

      {
        accumulated_people: accumulated_people,
        processed_urls: processed_urls,
        content_dirs: content_dirs
      }
    end

    def self.scrape_profiles(context, accumulated_people, processed_urls)
      content_dirs = []

      accumulated_people = accumulated_people.map do |person|
        next person if Services::Shared::People.all_contact_data_points_present?(person) && person["image"].present?
        next person if person["websites"].blank?

        person["websites"].each do |website|
          original_url = website["data"]
          next if original_url.blank?
          next if processed_urls.include?(original_url)

          puts "Fetching from #{original_url} for #{person["name"]}"
          url_content_dir, people = scrape_url_for_municipal_directory(
            context,
            original_url
          )

          next if people.blank?

          person_with_website_data = Validators::Utils.find_by_name(people, person["name"])

          next if person_with_website_data.blank?

          content_dirs << url_content_dir
          person = Services::Shared::People.merge_person(person, person_with_website_data)
        end

        person
      end

      [content_dirs, accumulated_people]
    end

    def self.scrape_url_for_municipal_directory(context, url)
      state = context[:state]
      city_entry = context[:city_entry]
      llm_service_string = context[:llm_service_string]
      page_fetcher = context[:page_fetcher]
      cache_path = context[:city_cache_path]
      government_type = context[:government_type]
      llm_service = get_llm_service(llm_service_string)

      puts "#{llm_service_string} Scraping #{url} for municipal directory"
      url_content_path = File.join(cache_path, Utils::UrlHelper.url_to_safe_folder_name(url))
      FileUtils.mkdir_p(url_content_path)

      content_file, image_map = page_fetcher.extract_content(url, url_content_path)
      return [nil, nil] unless content_file.present?

      local_context = { "state" => state, "city_entry" => city_entry, "government_type" => government_type }
      people = llm_service.extract_city_people(local_context, content_file, url)

      unless people.present? && people.is_a?(Array) && people.count.positive?
        return [nil,
                nil]
      end

      people_with_images = people.map do |person|
        maybe_add_source_image_to_person(person, image_map)
      end

      [url_content_path, people_with_images]
    end

    def self.maybe_add_source_image_to_person(person, image_map)
      return person if person["image"].blank?

      image_key = person["image"].gsub("images/", "")
      person["source_image"] = image_map[image_key]
      person
    end

    def self.get_llm_service(llm_service_string)
      case llm_service_string
      when "openai"
        Services::Openai.new
      when "gemini"
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
