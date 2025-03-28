module CityScrape
  class PageProcessor
    def initialize(state, engine, openai_service, data_fetcher, city_entry, city_directory)
      @engine = engine
      @openai_service = openai_service
      @data_fetcher = data_fetcher
      @city_entry = city_entry
      @state = state
      @city_directory = city_directory
    end

    def process_pages(search_results_to_process)
      dirs_with_people = []

      search_results_to_process.each_with_index do |url, index|
        partial_city_directory, candidate_dir = process_page(url, index)

        next unless partial_city_directory.present? && CityScrape::CityManager.includes_people?(partial_city_directory)

        dirs_with_people << candidate_dir
        @city_directory = CityScrape::CityManager.merge_directory(@city_directory, partial_city_directory, url)

        break if CityScrape::CityManager.valid_city_directory?(@city_directory)
      end

      [dirs_with_people, @city_directory]
    end 

    def process_page(url, index)
      puts "Fetching #{url}"
      candidate_dir = prepare_candidate_dir("#{@engine}_#{index}")
      content_file = @data_fetcher.extract_content(url, candidate_dir)
      return false unless content_file

      partial_city_directory = @openai_service.extract_city_info(content_file, url)

      [partial_city_directory, candidate_dir]
    end

    def prepare_candidate_dir(candidate_name)
      cache_directory = File.join(CityScrape::CityManager.get_city_path(@state, @city_entry), "cache")
      candidate_dir = File.join(cache_directory, candidate_name)
      FileUtils.mkdir_p(candidate_dir)

      candidate_dir
    end
  end
end
