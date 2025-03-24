# frozen_string_literal: true

# rake 'city_info:extract[wa,seattle,https://www.seattle.gov/council/meet-the-council]'
# rake 'city_info:extract[tx,austin,https://www.austintexas.gov/austin-city-council]'
# rake 'city_info:extract[nm,albuquerque,https://www.cabq.gov/council/find-your-councilor]'
# rake 'city_info:get_meta[wa,seattle]'
# rake 'city_info:find_geojson[nm,albuquerque,district]'

require_relative "../scrapers/city"
require_relative "../services/brave"
require_relative "../services/openai"
require_relative "../scrapers/us/wa/places"
require_relative "../scrapers/site_crawler"
require_relative "../scrapers/data_fetcher"
require_relative "../scrapers/common"

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

    state_directory_file = PathHelper.project_path(File.join("data", "us", state, "places.yml"))

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

    openai_service = Services::Openai.new
    data_fetcher = Scrapers::DataFetcher.new

    puts "Extracting city info for #{city.capitalize}, #{state.upcase}..."

    prepare_directories(state, city)
    updated_city_directory = initialize_city_directory(state, city)

    search_engines = %w[manual brave]
    search_result_urls = []
    source_dirs = []

    search_engines.each do |engine|
      search_result_urls = fetch_search_results(engine, state, city, state_city_entry["website"], search_result_urls)

      success, source_dirs = process_search_results(search_result_urls,
                                                    openai_service,
                                                    state,
                                                    city,
                                                    updated_city_directory,
                                                    source_dirs)

      break if success
    end

    finalize_city_directory(state, city, updated_city_directory, source_dirs)
  end

  desc "Generate PR comment for city directory"
  task :get_pr_comment, [:state, :city, :branch_name] do |_t, args|
    state = args[:state]
    city = args[:city]
    branch_name = args[:branch_name]

    base_image_url = "https://github.com/CivicPatch/open-data/blob/#{branch_name}/data/us/#{state}/#{city}"

    # Assuming you have a method to fetch the city data
    city_data = fetch_city_directory(state, city)

    markdown_content = <<~MARKDOWN
      # #{city.capitalize}, #{state.upcase}
      ## Sources
      #{city_data["sources"].join("\n")}
      ## People
      #{city_data["people"].map do |person|
        image_markdown = if person["image"].present?
          image_url = "#{base_image_url}/#{person["image"]}?raw=true"
          <<~IMAGE
            ![Image](#{image_url})
          IMAGE
        else
          "" # Ensure image_markdown is an empty string if no image is present
        end
        <<~PERSON
          * ## **Name:** #{person["name"]}
            **Position:** #{person["position"]}
            **Position Misc:** #{person["position_misc"]}
            **Email:** #{person["email"]}
            **Phone:** #{person["phone_number"]}
            **Website:** [Link](#{person["website"]})
            #{image_markdown}
        PERSON
      end.join("\n")}
    MARKDOWN

    puts markdown_content
  end

  private

  def fetch_city_directory(state, city)
    city_directory_file = PathHelper.project_path(File.join("data", "us", state, city, "directory.yml"))
    YAML.load(File.read(city_directory_file))
  end

  # Sometimes mayors end up in both the council members and city leaders arrays
  def deduplicate_people(council_members, city_leaders)
    council_members.each do |council_member|
      if city_leaders.any? { |leader| leader["name"] == council_member["name"] }
        city_leaders.delete_if { |leader| leader["name"] == council_member["name"] }
      end
    end

    [council_members, city_leaders]
  end

  def get_candidate_city_directory_urls(engine, state, city, website)
    keyword_groups = {
      "council_members" => ["mayor and city council",
                            "meet the council",
                            "city council members",
                            "council members",
                            "councilmembers",
                            "city council",
                            "government",
                            "council"],
      "city_leaders" => ["meet the mayor",
                         "about the mayor",
                         "mayor",
                         "council president"]
    }
    case engine
    when "manual"
      urls = Scrapers::SiteCrawler.get_urls(website, keyword_groups)
    when "brave"
      search_query = "#{city} #{state} city council members"
      urls = Services::Brave.get_search_result_urls(search_query, website, keyword_groups)
    end

    Scrapers::Common.urls_without_segments(urls, %w[news events])
  end

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
        new_place = existing_place.merge(place)
        state_directory["places"] = state_directory["places"].map { |p| p["place"] == place["place"] ? new_place : p }
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
    updated_city_directory,
    source_dirs
  )
    city_directory = PathHelper.project_path(File.join("data", "us", state, city))
    update_state_places(state, [{
                          "place" => city,
                          "last_city_scrape_run" => Time.now.strftime("%Y-%m-%d")
                        }])

    sources_destination_dir = PathHelper.project_path(File.join(city_directory, "city_scrape_sources"))
    FileUtils.mkdir_p(sources_destination_dir)

    images_dir = PathHelper.project_path(File.join(city_directory, "images"))
    FileUtils.mkdir_p(images_dir)

    source_dirs.each do |source_dir|
      # store images in combined images directory
      puts "Copying images from #{source_dir}/images/* to #{images_dir}"
      Dir.glob("#{source_dir}/images/*").each do |image|
        FileUtils.cp(image, images_dir)
      end

      FileUtils.mv(source_dir, sources_destination_dir)
    end

    city_info_file = PathHelper.project_path(File.join(city_directory, "directory.yml"))

    File.write(city_info_file, updated_city_directory.to_yaml)
  end

  def people_with_names(people)
    people.select { |person| person["name"].present? }
  end

  def merge_people_lists(list1, list2)
    # Create a hash to store merged people by full name
    people_hash = {}

    # Helper method to generate full name
    full_name = ->(person) { "#{person["name"].split.first} #{person["name"].split.last}" }

    # Add people from the first list
    list1.each do |person|
      name_key = full_name.call(person)
      people_hash[name_key] ||= person.dup # Use dup to avoid modifying the original object
    end

    # Merge people from the second list
    list2.each do |person|
      name_key = full_name.call(person)
      if people_hash[name_key]
        # Merge properties if the person already exists, prefer properties from the first list unless the first list is empty
        people_hash[name_key].merge!(person) { |_key, old_val, new_val| old_val.present? ? old_val : new_val }
      else
        people_hash[name_key] = person.dup
      end
    end

    # Convert the hash back to an array
    people_hash.values
  end

  def initialize_city_directory(state, city)
    {
      "ocd_id" => "ocd-division/country:us/state:#{state}/place:#{city}",
      "people" => [],
      "sources" => []
    }
  end

  def fetch_search_results(engine, state, city, website, existing_urls)
    new_results = get_candidate_city_directory_urls(engine, state, city, website)
    existing_urls.concat(new_results).uniq!

    puts "Search engine #{engine} found #{new_results.count} urls"
    puts new_results.join("\n")

    existing_urls
  end

  def process_search_results(
    search_result_urls,
    openai_service,
    state, city,
    updated_city_directory,
    source_dirs)
    city_directory = PathHelper.project_path(File.join("data", "us", state, city))
    cache_destination_dir = PathHelper.project_path(File.join(city_directory, "cache"))

    search_pointer = 0

    data_fetcher = Scrapers::DataFetcher.new

    while search_pointer < search_result_urls.count
      url = search_result_urls[search_pointer]
      search_pointer += 1

      puts "Fetching #{url}"
      candidate_dir = prepare_candidate_dir(cache_destination_dir, search_pointer)
      content_file = fetch_content(data_fetcher, url, candidate_dir)

      next unless content_file

      page_city_info = extract_city_info(openai_service, state, city, content_file, url)

      next unless page_city_info && page_city_info["people"].present?
      
      source_dirs << candidate_dir

      update_city_directory_with_info(updated_city_directory, page_city_info, url)

      council_member_count = updated_city_directory["people"].select { |person| person["position"] == "council_member" }.count
      city_leader_count = updated_city_directory["people"].select { |person| %w[mayor].include?(person["position"]) }.count

      puts "council_member_count: #{council_member_count}, city_leader_count: #{city_leader_count}"
      return [true, source_dirs] if council_member_count > 1 && city_leader_count.positive?

    end

    [false, source_dirs]
  end

  def update_city_directory_with_info(city_directory, page_city_info, url)
    new_people = people_with_names(page_city_info["people"])
    return unless new_people.present?

    city_directory["people"] = merge_people_lists(city_directory["people"], new_people)
    city_directory["sources"] << url
  end

  def finalize_city_directory(state, city, updated_city_directory, source_dirs)
    cache_directory = PathHelper.project_path(File.join("data", "us", state, city, "cache"))
    if updated_city_directory["people"].length > 1
      update_city_directory(state, city, updated_city_directory, source_dirs)
      FileUtils.rm_rf(cache_directory)
      puts "✅ Successfully extracted city info"
      puts "Data saved to: #{PathHelper.project_path(File.join("data", "us", state, city, "directory.yml"))}"
      exit 0 # Exit if successful
    else
      puts "❌ Error: No valid city info extracted"
      exit 1
    end
  end
end
