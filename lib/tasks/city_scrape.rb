# frozen_string_literal: true

# rake 'city_info:extract[wa,seattle,https://www.seattle.gov/council/meet-the-council]'
# rake 'city_info:extract[tx,austin,https://www.austintexas.gov/austin-city-council]'
# rake 'city_info:extract[nm,albuquerque,https://www.cabq.gov/council/find-your-councilor]'
# rake 'city_info:get_meta[wa,seattle]'
# rake 'city_info:find_geojson[nm,albuquerque,district]'

require_relative "../scrapers/city"
require_relative "../services/openai"
require_relative "../scrapers/us/wa/places"
require_relative "../scrapers/site_crawler"
require_relative "../scrapers/data_fetcher"

namespace :city_scrape do
  desc "Pick cities from queue"
  task :pick_cities, [:state, :num_cities, :cities_to_ignore] do |_t, args|
    state = args[:state]
    num_cities = args[:num_cities]
    cities_to_ignore = args[:cities_to_ignore].present? ? args[:cities_to_ignore].split(" ") : []

    if state.blank? || num_cities.blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:pick_cities[state,num_cities]'"
      puts "Example: rake 'city_info:pick_cities[wa,10]'"
      exit 1
    end

    state_directory_file = PathHelper.project_path(File.join("data", "us", state, "directory.yml"))

    unless File.exist?(state_directory_file)
      puts "Error: State directory file not found at #{state_directory_file}"
      exit 1
    end

    state_directory = YAML.load(File.read(state_directory_file))

    cities = state_directory["places"].select do |c|
      !cities_to_ignore.include?(c["place"]) &&
        c["last_city_scrape_run"].nil? && c["website"].present?
    end.first(num_cities.to_i)

    puts cities.map { |c| c["place"] }.join(",")
  end

  desc "Find official cities for a state"
  task :get_places, [:state] do |_t, args|
    state = args[:state]

    scraper = case state
              when "wa"
                Scrapers::Us::Wa::Directory
              else
                raise "Unsupported state: #{state}"
              end

    if state.blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:get_places[state]'"
      puts "Example: rake 'city_info:get_places[wa]'"
      exit 1
    end

    new_places = scraper.get_places

    update_state_places(state, new_places)
  end

  desc "Find city geojson data"
  task :find_division_map, %i[state city] => :environment do |_t, args|
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
      candidate_division_maps
    )

    if found_map
      puts "✅ Found valid division map"
      save_division_data(state, city, candidate_map, division_type)
    else
      puts "❌ Error: No valid division map found"
      exit 1
    end

    cities_yaml = YAML.load(File.read(Rails.root.join("data", state, "cities.yml")))
    cities_yaml["cities"].find do |c|
      c["city"] == city
    end["last_city_info_division_map_run"] = Time.now.strftime("%Y-%m-%d")
    File.write(Rails.root.join("data", state, "cities.yml"), cities_yaml.to_yaml)
  end

  desc "Extract city info for a specific city"
  task :fetch, [:state, :city] do |_t, args|
    state = args[:state]
    city = args[:city]

    state_city_entry = validate_fetch_inputs(state, city)

    Scrapers::City.new
    openai_service = Services::Openai.new
    data_fetcher = Scrapers::DataFetcher.new

    puts "Extracting city info for #{city.capitalize}, #{state.upcase}..."

    destination_dir, cache_destination_dir = prepare_directories(state, city)
    search_result_urls = Scrapers::SiteCrawler.get_urls(state_city_entry["website"], {
                                                          "mayor" => ["mayor"],
                                                          "council_members" => ["city council members",
                                                                                "council members", "councilmembers", "city council", "council"]
                                                        })

    puts "Found #{search_result_urls.count} search result urls:"
    puts search_result_urls.join("\n")

    city_directory = {
      "council_members" => [], # active council members
      "city_leaders" => [], # ex mayor, city manager, etc
      "sources" => []
    }

    source_dirs = []

    search_result_urls.each_with_index do |url, index|
      break if city_directory["council_members"].count.positive? && city_directory["city_leaders"].count.positive?

      candidate_dir = prepare_candidate_dir(cache_destination_dir, index)
      puts "Fetching #{url}"

      content_file = fetch_content(data_fetcher, url, candidate_dir)

      unless content_file
        puts "❌ Error extracting content from #{url}"
        next
      end

      updated_city_info = extract_city_info(openai_service, state, city, content_file, url)

      next unless updated_city_info

      council_members = people_with_names(updated_city_info["council_members"])
      city_leaders = people_with_names(updated_city_info["city_leaders"])

      if council_members.present?
        city_directory["council_members"] = merge_arrays_by_field(
          city_directory["council_members"], updated_city_info["council_members"], "name"
        )
      end

      if city_leaders.present?
        city_directory["city_leaders"] = merge_arrays_by_field(
          city_directory["city_leaders"], updated_city_info["city_leaders"], "name"
        )
      end

      city_directory["sources"] << url
      source_dirs << candidate_dir
    end

    # Are mayors important?
    if city_directory["council_members"].present?
      update_city_directory(
        state,
        city,
        city_directory,
        destination_dir,
        source_dirs
      )
      FileUtils.rm_rf(cache_destination_dir)
      puts "✅ Successfully extracted city info"
      puts "Data saved to: #{PathHelper.project_path(File.join("data", "us", state, city, "directory.yml"))}"
      exit 0 # Exit if successful
    else
      puts "❌ Error: No valid city info extracted"
      exit 1
    end
  end

  private

  def validate_find_division_map_inputs(state, city)
    raise "Error: Missing required parameters state: #{state} and city: #{city}" if state.blank? || city.blank?

    info_file = Rails.root.join("data", state, city, "info.yml")
    raise "Error: City info file not found at #{info_file}" unless File.exist?(info_file)

    info_yaml = YAML.load(File.read(info_file))
    info_yaml["division_type"]
  end

  def find_division_map_urls(map_finder, state, city, division_type)
    search_query = "#{city} #{state} city council #{division_type}s map"
    search_result_urls = Services::Brave.get_search_result_urls(search_query, nil, ["county"])

    candidate_urls = []
    search_result_urls.each do |url|
      candidate_map_urls = map_finder.find_candidate_maps(url)
      candidate_urls << candidate_map_urls if candidate_map_urls.any?
    end

    candidate_urls = candidate_urls.flatten.uniq
  end

  # TODO: -- probably can just do this naively via district/ward search properties
  def process_candidate_division_maps(openai_service, state, city, division_type, candidate_division_maps)
    candidate_division_maps.each do |candidate_map|
      response = openai_service.extract_city_division_map_data(
        state, city, division_type,
        candidate_map[:file_path],
        candidate_map[:url]
      )

      if is_valid_division_map?(response)
        return [true, candidate_map] # Successfully found a valid division map
      end
    end
    [false, nil] # No valid division map found
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

    result = MapFinder.format_properties(state, city, candidate_map[:file_path], [division_type])

    source_path = Rails.root.join("data", state, city, "map_source", "division_map.geojson")
    FileUtils.mkdir_p(source_path)
    FileUtils.mv(candidate_map[:file_path], source_path)

    File.write(destination_path, result)
  end

  def update_state_places(state, updated_places)
    state_directory_file = PathHelper.project_path(File.join("data", "us", state, "places.yml"))
    state_directory = {
      "ocd_id" => "ocd-division/country:us/state:#{state}",
      "places" => []
    }

    state_directory = YAML.load(File.read(state_directory_file)) if File.exist?(state_directory_file)

    updated_places.each do |place|
      existing_place = state_directory["places"].find { |p| p["place"] == place["place"] }
      if existing_place
        existing_place.merge!(place)
      else
        state_directory["places"] << place
      end
    end

    File.open(state_directory_file, "w") do |file|
      file.write(state_directory.to_yaml)
    end
  end

  def prepare_candidate_dir(cache_destination_dir, index)
    candidate_dir = PathHelper.project_path(File.join(cache_destination_dir, "candidate_#{index}"))
    FileUtils.mkdir_p(candidate_dir)

    candidate_dir
  end

  def validate_fetch_inputs(state, city)
    if state.blank? || city.blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:fetch[state,city]'"
      puts "Example: rake 'city_info:fetch[wa,seattle]'"
      exit 1
    end

    state_directory_file = PathHelper.project_path(File.join("data", "us", state, "places.yml"))
    state_directory = YAML.load(File.read(state_directory_file))
    city_entry = state_directory["places"].find { |p| p["place"] == city }

    if city_entry["website"].blank?
      puts "❌ Error: City website not found for #{city.capitalize}, #{state.upcase}"
      exit 1
    end

    city_entry
  end

  def prepare_directories(state, city)
    destination_dir = PathHelper.project_path(File.join("data", "us", state, city))
    cache_destination_dir = PathHelper.project_path(File.join("data", "us", state, city, "cache"))

    FileUtils.mkdir_p(destination_dir)
    FileUtils.mkdir_p(cache_destination_dir)
    FileUtils.rm_rf(PathHelper.project_path(File.join("data", "us", state, city, "city_scrape_sources")))

    [destination_dir, cache_destination_dir]
  end

  def fetch_content(data_fetcher, url, candidate_dir)
    data_fetcher.extract_content(url, candidate_dir)
  rescue StandardError => e
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

  def update_city_directory(
    state,
    city,
    city_directory_content,
    destination_dir,
    source_dirs
  )
    update_state_places(state, [{
                          "place" => city,
                          "last_city_scrape_run" => Time.now.strftime("%Y-%m-%d")
                        }])

    sources_destination_dir = PathHelper.project_path(File.join(destination_dir, "city_scrape_sources"))
    FileUtils.mkdir_p(sources_destination_dir)

    images_dir = PathHelper.project_path(File.join(destination_dir, "images"))
    FileUtils.mkdir_p(images_dir)

    source_dirs.each do |source_dir|
      # store images in combined images directory
      puts "Copying images from #{source_dir}/images/* to #{images_dir}"
      Dir.glob("#{source_dir}/images/*").each do |image|
        FileUtils.cp(image, images_dir)
      end

      FileUtils.mv(source_dir, sources_destination_dir)
    end

    city_info_file = PathHelper.project_path(File.join("data", "us", state, city, "directory.yml"))
    normalized_city_directory = normalize_city_directory(state, city, city_directory_content)

    File.write(city_info_file, normalized_city_directory.to_yaml)
  end

  def normalize_city_directory(state, city, city_directory_content)
    city_directory = {
      "ocd_id" => "ocd-division/country:us/state:#{state}/place:#{city}",
      "people" => [],
      "sources" => city_directory_content["sources"]
    }

    city_directory_content["city_leaders"].each do |person|
      person["position"] = person["position"]&.downcase || "city_leader"
      city_directory["people"] << person
    end

    city_directory_content["council_members"].each do |person|
      person["position"] = "council_member"
      city_directory["people"] << person
    end

    city_directory
  end

  def merge_objects_by_field(obj1, obj2, field)
    return nil unless obj1[field] == obj2[field] # Check if they refer to the same object

    merged = obj1.dup # Start with a duplicate of the first object
    obj2.each do |key, value|
      merged[key] = value if value.present? # Merge properties, preferring non-nil values
    end
    merged
  end

  def merge_arrays_by_field(arr1, arr2, field)
    merged = []

    # Create a hash for quick lookup of objects in arr2 by the specified field
    lookup = arr2.each_with_object({}) { |obj, hash| hash[obj[field]] = obj }

    arr1.each do |obj1|
      merged << if lookup[obj1[field]]
                  # Merge the matching object from arr2 with obj1
                  merge_objects_by_field(obj1, lookup[obj1[field]], field)
                else
                  # If no match found, just add obj1 to the merged array
                  obj1
                end
    end

    # Add any objects from arr2 that were not in arr1
    arr2.each do |obj2|
      merged << obj2 unless arr1.any? { |obj1| obj1[field] == obj2[field] }
    end

    merged
  end

  def people_with_names(people)
    people.select { |person| person["name"].present? }
  end
end
