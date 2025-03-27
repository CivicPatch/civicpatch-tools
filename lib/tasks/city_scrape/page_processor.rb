module CityScrape
  class PageProcessor
    def initialize(state, engine, openai_service, data_fetcher, city_entry)
      @engine = engine
      @openai_service = openai_service
      @data_fetcher = data_fetcher
      @city_entry = city_entry
      @state = state
    end

    def process_page(url, index)
      puts "Fetching #{url}"
      candidate_dir = prepare_candidate_dir("#{@engine}_#{index}")
      content_file = fetch_content(url, candidate_dir)
      return false unless content_file

      partial_city_directory = extract_city_info(content_file, url)

      return [nil, nil] unless partial_city_directory.present?

      [partial_city_directory, candidate_dir]
    end

    def prepare_candidate_dir(candidate_name)
      cache_directory = File.join(CityScrape::CityManager.get_city_path(@state, @city_entry), "cache")
      candidate_dir = File.join(cache_directory, candidate_name)
      FileUtils.mkdir_p(candidate_dir)

    end
  end
end
