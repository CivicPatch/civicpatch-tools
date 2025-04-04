module CityScraper
  class DirectoryExtractor
    def initialize(state, engine, openai_service, data_fetcher, city_entry, city_directory)
      @state = state
      @engine = engine
      @openai_service = openai_service
      @data_fetcher = data_fetcher
      @city_entry = city_entry
      @city_directory = city_directory
    end

    def process_city_pages(search_results)
      directories_with_people = []
      new_city_directory = @city_directory

      search_results.each_with_index do |url, index|
        directory, partial_directory = fetch_and_process_page(url, index)
        next unless valid_partial_directory?(partial_directory)

        directories_with_people << directory
        new_city_directory = merge_city_directories(new_city_directory, partial_directory)

        council_members = CityScrape::CityManager.get_council_members_count(new_city_directory)
        mayors = CityScrape::CityManager.get_mayors_count(new_city_directory)

        puts "Processed url: #{url} -> Council members: #{council_members}, Mayors: #{mayors}"
        break if city_directory_valid?(new_city_directory)
      end

      [directories_with_people, new_city_directory]
    end

    private

    def fetch_and_process_page(url, index)
      puts "Fetching #{url}"
      directory = create_candidate_directory(index)
      content = @data_fetcher.extract_content(url, directory)
      partial_directory = extract_partial_directory(content, url)
      [directory, partial_directory]
    end

    def extract_partial_directory(content, url)
      return nil unless content

      @openai_service.extract_city_info(content, url)
    end

    def create_candidate_directory(index)
      directory_name = "#{@engine}_#{index}"
      cache_dir = File.join(PathHelper.get_city_path(@state, @city_entry["gnis"]), "cache")
      directory_path = File.join(cache_dir, directory_name)
      FileUtils.mkdir_p(directory_path)
      directory_path
    end

    def valid_partial_directory?(partial_directory)
      CityScrape::CityManager.includes_people?(partial_directory)
    end

    def merge_city_directories(city_directory, partial_directory)
      CityScrape::CityManager.merge_directory(city_directory, partial_directory)
    end

    def city_directory_valid?(city_directory)
      CityScrape::CityManager.valid_city_directory?(city_directory)
    end
  end
end
