# rake 'city_info:extract[wa,seattle,https://www.seattle.gov/council/meet-the-council]'
# rake 'city_info:extract[tx,austin,https://www.austintexas.gov/austin-city-council]'
# rake 'city_info:extract[nm,albuquerque,https://www.cabq.gov/council/find-your-councilor]'
# rake 'city_info:get_meta[wa,seattle]'
# rake 'city_info:find_geojson[nm,albuquerque,district]'

require_relative "../data_fetcher"
require_relative "../services/openai"
require_relative "../services/brave"
require_relative "../scrapers/wa"
require_relative "../scrapers/site_crawler"

namespace :city_info do
  desc "Pick cities from queue"
  task :pick_cities, [ :state, :num_cities, :cities_to_ignore ] => :environment do |t, args|
    state = args[:state]
    num_cities = args[:num_cities]
    cities_to_ignore = args[:cities_to_ignore].present? ? args[:cities_to_ignore].split(" ") : []

    if state.blank? || num_cities.blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:pick_cities[state,num_cities]'"
      puts "Example: rake 'city_info:pick_cities[wa,10]'"
      exit 1
    end

    state_info_file = Rails.root.join("data", state, "state_info.yml")

    if !File.exist?(state_info_file)
      puts "Error: State info file not found at #{state_info_file}"
      exit 1
    end

    state_info = YAML.load(File.read(state_info_file))

    cities = state_info["places"].select { |c|
      !cities_to_ignore.include?(c["place"]) &&
      c["last_city_info_council_members_run"].nil? && c["website"].present?
    }.first(num_cities.to_i)

    puts cities.map { |c| c["place"] }.join(",")
  end

  desc "Find official cities for a state"
  task :scrape_state_dir, [ :state ] => :environment do |t, args|
    state = args[:state]

    if state.blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:find_official_city_websites[state]'"
      puts "Example: rake 'city_info:find_official_city_websites[wa]'"
      exit 1
    end

    new_places = Scrapers::Wa.get_places

    update_state_info(state, new_places)
  end

  desc "Find city geojson data"
  task :find_division_map, [ :state, :city ] => :environment do |t, args|
    state = args[:state]
    city = args[:city]

    begin
      division_type = validate_find_division_map_inputs(state, city)
    rescue StandardError => e
      raise "Error: #{e.message}"
    end

    openai_service = Services::Openai.new
    map_finder = MapFinder.new(state, city)

    candidate_urls = find_division_map_urls(map_finder, state, city, division_type)

    puts "Found #{candidate_urls.count} candidate city #{division_type} maps; #{candidate_urls.join("\n")}"

    candidate_division_maps = map_finder.download_geojson_urls(candidate_urls)

    found_map, candidate_map = process_candidate_division_maps(
      openai_service,
      state, city,
      division_type,
      candidate_division_maps)

    if found_map
      puts "✅ Found valid division map"
      save_division_data(state, city, candidate_map, division_type)
    else
      puts "❌ Error: No valid division map found"
      exit 1
    end

    cities_yaml = YAML.load(File.read(Rails.root.join("data", state, "cities.yml")))
    cities_yaml["cities"].find { |c| c["city"] == city }["last_city_info_division_map_run"] = Time.now.strftime("%Y-%m-%d")
    File.write(Rails.root.join("data", state, "cities.yml"), cities_yaml.to_yaml)
  end

  desc "Extract city info for a specific city"
  task :fetch, [ :state, :city ] => :environment do |t, args|
    state = args[:state]
    city = args[:city]

    state_city_entry = validate_search_and_extract_inputs(state, city)

    data_fetcher = DataFetcher.new
    openai_service = Services::Openai.new

    puts "Extracting city info for #{city.capitalize}, #{state.upcase}..."

    destination_dir, cache_destination_dir = prepare_directories(state, city)

    search_engines = [ "manual", "brave" ]
    search_result_urls = []

    search_engines.each do |engine|
      puts "Fetching search result urls from #{engine}"
      search_result_urls = fetch_search_result_urls(engine, city, state, state_city_entry["website"])
      next if search_result_urls.empty?

      puts "Found #{search_result_urls.count} search result urls from #{engine}:"
      puts search_result_urls.join("\n")

      search_result_urls.each_with_index do |url, index|
        candidate_dir = prepare_candidate_dir(cache_destination_dir, index)

        puts "Fetching #{url}"

        content_file = fetch_content(data_fetcher, url, candidate_dir)
        unless content_file
          puts "❌ Error extracting content from #{url}"
          next
        end

        updated_city_info = extract_city_info(openai_service, state, city, content_file, url)
        if updated_city_info
          update_city_info(
            state,
            city,
            state_city_entry,
            updated_city_info,
            destination_dir,
            candidate_dir,
            cache_destination_dir
          )
          puts "✅ Successfully extracted city info"
          puts "Data saved to: #{Rails.root.join('data', state, city, 'info.yml')}"
          exit 0 # Exit if successful
        else
          puts "❌ Error with response from OpenAI"
        end
      end
    end

    puts "❌ Error: No valid city info extracted from any search engine"
    exit 1
  end

  private

  def validate_find_division_map_inputs(state, city)
    if state.blank? || city.blank?
      raise "Error: Missing required parameters state: #{state} and city: #{city}"
    end

    info_file = Rails.root.join("data", state, city, "info.yml")
    if !File.exist?(info_file)
      raise "Error: City info file not found at #{info_file}"
    end

    info_yaml = YAML.load(File.read(info_file))
    division_type = info_yaml["division_type"]

    division_type
  end

  def find_division_map_urls(map_finder, state, city, division_type)
    search_query = "#{city} #{state} city council #{division_type}s map"
    search_result_urls = Services::Brave.get_search_result_urls(search_query, nil, [ "county" ])

    candidate_urls = []
    search_result_urls.each do |url|
      candidate_map_urls = map_finder.find_candidate_maps(url)
      if candidate_map_urls.any?
        candidate_urls << candidate_map_urls
      end
    end

    candidate_urls = candidate_urls.flatten.uniq
  end

  # TODO -- probably can just do this naively via district/ward search properties
  def process_candidate_division_maps(openai_service, state, city, division_type, candidate_division_maps)
    candidate_division_maps.each do |candidate_map|
      response = openai_service.extract_city_division_map_data(
        state, city, division_type,
        candidate_map[:file_path],
        candidate_map[:url])

      if is_valid_division_map?(response)
        return [ true, candidate_map ] # Successfully found a valid division map
      end
    end
    [ false, nil ] # No valid division map found
  end

  def is_valid_division_map?(results)
    results["has_division_data"] == "true" && results["has_city_data"] == "true"
  end

  def save_division_data(state, city, candidate_map, division_type)
      info_file_path = Rails.root.join("data", state, city, "info.yml")
      info_yaml = YAML.load(File.read(info_file_path))
      info_yaml["arcgis_map_url"] = candidate_map[:url]

      File.write(info_file_path, info_yaml.to_yaml)

      destination_path = Rails.root.join("data", state, city, "division_map.geojson")

      result = MapFinder.format_properties(state, city, candidate_map[:file_path], [ division_type ])

      source_path = Rails.root.join("data", state, city, "map_source", "division_map.geojson")
      FileUtils.mkdir_p(source_path)
      FileUtils.mv(candidate_map[:file_path], source_path)

      File.write(destination_path, result)
  end

  def update_state_info(state, updated_places)
    state_info_file = Rails.root.join("data", state, "state_info.yml")
    state_info = {
      "ocd_id" => "ocd-division/country:us/state:#{state}",
      "places" => []
    }

    if File.exist?(state_info_file)
      state_info = YAML.load(File.read(state_info_file))
    end

    # merge cities with existing places
    original_places = state_info["places"].map { |p| [ p["place"], p ] }.to_h

    # exclude the scraper_misc field from the places
    new_places = updated_places.map { |p| [ p["place"], p.except("scraper_misc") ] }.to_h

    # First merge existing places with updates
    merged_places = original_places.merge(new_places)

    state_info["places"] = merged_places.values

    File.open(state_info_file, "w") do |file|
      file.write(state_info.to_yaml)
    end
  end

  def prepare_candidate_dir(cache_destination_dir, index)
    candidate_dir = Rails.root.join(cache_destination_dir, "candidate_#{index}")
    FileUtils.mkdir_p(candidate_dir)

    candidate_dir
  end

  def validate_search_and_extract_inputs(state, city)
     if state.blank? || city.blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:search_and_extract[state,city]'"
      puts "Example: rake 'city_info:search_and_extract[wa,seattle]'"
      exit 1
     end

    state_info_file = Rails.root.join("data", state, "state_info.yml")
    state_info = YAML.load(File.read(state_info_file))
    city_entry = state_info["places"].find { |p| p["place"] == city }

    if city_entry["website"].blank?
      puts "❌ Error: City website not found for #{city.capitalize}, #{state.upcase}"
      exit 1
    end

    city_entry
  end

  def prepare_directories(state, city)
    destination_dir = Rails.root.join("data", state, city)
    cache_destination_dir = Rails.root.join("data", state, city, "cache")

    FileUtils.mkdir_p(destination_dir)
    FileUtils.mkdir_p(cache_destination_dir)

    [ destination_dir, cache_destination_dir ]
  end

  def fetch_search_result_urls(search_engine, city, state, website)
    case search_engine
    when "manual"
      Scrapers::SiteCrawler.get_urls(website, [ "city council members", "council members", "councilmembers", "city council", "mayor", "council" ])
    when "brave"
      Services::Brave.get_search_result_urls("#{city} #{state} city council members", website)
    else
      raise "Invalid search engine: #{search_engine}"
    end
  end

  def fetch_content(data_fetcher, url, candidate_dir)
    data_fetcher.extract_content(url, candidate_dir)
  rescue => e
    puts "Error fetch_content: #{e.message}"
    puts "Error backtrace: #{e.backtrace.join("\n")}"
    nil
  end

  def extract_city_info(openai_service, state, city, content_file, url)
    updated_city_info = openai_service.extract_city_info(state, city, content_file, url)

    if updated_city_info.is_a?(Hash) && updated_city_info.key?("error")
      nil
    else
      updated_city_info["council_url_site"] = url
      updated_city_info
    end
  end

  def update_city_info(
    state,
    city,
    state_city_entry,
    updated_city_info,
    destination_dir,
    candidate_dir,
    cache_destination_dir)
    state_city_entry["last_city_info_council_members_run"] = Time.now.strftime("%Y-%m-%d")
    update_state_info(state, [ state_city_entry ])

    FileUtils.rm_rf(Rails.root.join(destination_dir, "city_council_source"))
    FileUtils.mv(candidate_dir, Rails.root.join(destination_dir, "city_council_source"))

    city_info_file = Rails.root.join("data", state, city, "info.yml")
    city_info_yaml = if File.exist?(city_info_file)
                       existing_info = YAML.load(File.read(city_info_file))
                       existing_info.merge(updated_city_info)
    else
                       updated_city_info
    end

    File.write(city_info_file, city_info_yaml.to_yaml)
    FileUtils.rm_rf(cache_destination_dir)
  end
end
