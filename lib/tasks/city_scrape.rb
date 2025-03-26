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
require_relative "../scrapers/us/mi/places"
require_relative "../scrapers/site_crawler"
require_relative "../scrapers/data_fetcher"
require_relative "../scrapers/common"

namespace :city_scrape do
  desc "Pick cities from queue"
  task :pick_cities, [:state, :num_cities, :gnis_to_ignore] do |_t, args| # bug -- this is a list of city names, which is not a unique identifier
    state = args[:state]
    num_cities = args[:num_cities]
    gnis_to_ignore = args[:gnis_to_ignore].present? ? args[:gnis_to_ignore].split(" ") : []

    validate_pick_cities(state, num_cities)

    state_directory_file = PathHelper.project_path(File.join("data", "us", state, "places.yml"))

    unless File.exist?(state_directory_file)
      puts "Error: State directory file not found at #{state_directory_file}"
      exit 1
    end

    state_directory = YAML.load(File.read(state_directory_file))

    cities = state_directory["places"].select do |c|
      !gnis_to_ignore.include?(c["gnis"]) &&
        c["last_city_scrape_run"].nil? && c["website"].present?
    end.first(num_cities.to_i)

    puts cities.map { |c| c["gnis"] }.join(",")
  end

  desc "Find official cities for a state"
  task :get_places, [:state] do |_t, args|
    if args[:state].blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:get_places[state]'"
      puts "Example: rake 'city_info:get_places[wa]'"
      exit 1
    end

    state = args[:state]

    scraper = case state
              when "wa"
                Scrapers::Us::Wa::Directory
              when "mi"
                Scrapers::Us::Mi::Directory
              else
                raise "Unsupported state: #{state}"
              end

    if state.blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:get_places[state]'"
      puts "Example: rake 'city_info:get_places[wa]'"
      exit 1
    end

    new_places = scraper.fetch_places
    update_state_places(state, new_places)
  end

  #desc "Find city geojson data"
  #task :find_division_map, %i[state city] => :environment do |_t, args|
  #  state = args[:state]
  #  city = args[:city]

  #  begin
  #    division_type = validate_find_division_map_inputs(state, city)
  #  rescue StandardError => e
  #    raise "Error: #{e.message}"
  #  end

  #  openai_service = Services::Openai.new
  #  map_finder = MapFinder.new(state, city)

  #  candidate_urls = find_division_map_urls(map_finder, state, city, division_type)

  #  puts "Found #{candidate_urls.count} candidate city #{division_type} maps; #{candidate_urls.join("\n")}"

  #  candidate_division_maps = map_finder.download_geojson_urls(candidate_urls)

  #  found_map, candidate_map = process_candidate_division_maps(
  #    openai_service,
  #    state, city,
  #    division_type,
  #    candidate_division_maps
  #  )

  #  if found_map
  #    puts "✅ Found valid division map"
  #    save_division_data(state, city, candidate_map, division_type)
  #  else
  #    puts "❌ Error: No valid division map found"
  #    exit 1
  #  end

  #  cities_yaml = YAML.load(File.read(Rails.root.join("data", state, "cities.yml")))
  #  cities_yaml["cities"].find do |c|
  #    c["city"] == city
  #  end["last_city_info_division_map_run"] = Time.now.strftime("%Y-%m-%d")
  #  File.write(Rails.root.join("data", state, "cities.yml"), cities_yaml.to_yaml)
  #end

  desc "Extract city info for a specific city"
  task :fetch, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    state_city_entry = validate_fetch_inputs(state, gnis)
    city = state_city_entry["name"]

    openai_service = Services::Openai.new
    Scrapers::DataFetcher.new

    puts "Extracting city info for #{city.capitalize}, #{state.upcase}..."

    cache_directory = prepare_directories(state, state_city_entry)
    city_directory = {
      "people" => [],
      "sources" => []
    }

    search_engines = %w[manual brave]
    search_result_urls = []
    source_dirs = []

    search_engines.each do |engine|
      search_result_urls = fetch_search_results(engine, state_city_entry, search_result_urls)

      success, source_dirs, city_directory = process_search_results(engine,
                                                                    search_result_urls,
                                                                    openai_service,
                                                                    city_directory,
                                                                    source_dirs,
                                                                    cache_directory)

      break if success
    end

    finalize_city_directory(state, state_city_entry, city_directory, source_dirs)
  end

  desc "Generate PR comment for city directory"
  task :get_pr_comment, [:state, :gnis, :branch_name] do |_t, args|
    gnis = args[:gnis]
    branch_name = args[:branch_name]

    state_city_entry = validate_fetch_inputs(state, gnis)
    state = state_city_entry["state"]
    city = state_city_entry["name"]
    city_directory_path = get_city_directory_path(state, state_city_entry)
    relative_path = city_directory_path[city_directory_path.index("data")..-1]

    base_image_url = "https://github.com/CivicPatch/open-data/blob/#{branch_name}/#{relative_path}"

    city_data = YAML.load(File.read(get_city_directory_file(state_city_entry)))

    markdown_content = <<~MARKDOWN
      # #{city.capitalize}, #{state.upcase}
      ## Sources
      #{city_data["sources"].join("\n")}
      ## People
      #{city_data["people"].map do |person|
        image_markdown = if person["image"].present?
                           image_url = "#{base_image_url}/#{person["image"]}?raw=true"
                           <<~IMAGE
                             <img src="#{image_url}" width="150" />)
                           IMAGE
                         else
                           "" # Ensure image_markdown is an empty string if no image is present
                         end
        <<~PERSON
          ## **Name:** #{person["name"]}
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

 
  desc "Count all cities without fips"
  task :count_cities_without_fips do
    state_directory_file = PathHelper.project_path(File.join("data", "us", "wa", "places.yml"))
    state_directory = YAML.load(File.read(state_directory_file))
    without_fips =  state_directory["places"].select { |p| p["fips"].blank? }
    without_gnis =  state_directory["places"].select { |p| p["gnis"].blank? }
    puts without_fips.count
    puts without_fips.map { |p| p["name"] }.join(", ")
    puts without_gnis.count
    puts without_gnis.map { |p| p["name"] }.join(", ")
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

  def get_candidate_city_directory_urls(engine, state_city_entry)
    city = state_city_entry["name"]
    state = state_city_entry["state"]
    # type = city_entry["type"] TODO: fix
    website = state_city_entry["website"]

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

    Scrapers::Common.urls_without_segments(urls, %w[news events event])
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

    updated_places.each do |updated_place|
      existing_place_index = state_directory["places"].find_index { |p| p["gnis"] == updated_place["gnis"] }
      if existing_place_index
        existing_place = state_directory["places"][existing_place_index]

        merged = existing_place.merge(updated_place) { |_key, old_val, new_val| new_val.present? ? new_val.dup : old_val.dup }
        state_directory["places"][existing_place_index] = merged
      else
        state_directory["places"] << updated_place
      end


    end

    File.open(state_directory_file, "w") do |file|
      file.write(state_directory.to_yaml)
    end
  end

  def prepare_candidate_dir(cache_directory, candidate_name)
    candidate_dir = File.join(cache_directory, candidate_name)
    FileUtils.mkdir_p(candidate_dir)

    candidate_dir
  end

  def validate_fetch_inputs(state, gnis)
    state_directory_file = PathHelper.project_path(File.join("data", "us", state, "places.yml"))
    state_directory = YAML.load(File.read(state_directory_file))
    state_city_entry = state_directory["places"].find { |p| p["gnis"] == gnis }

    city = state_city_entry["name"]

    if state.blank? || city.blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:fetch[wa,gnis]'"
      exit 1
    end

    if state_city_entry["website"].blank?
      puts "❌ Error: City website not found for #{city.capitalize}, #{state.upcase}"
      exit 1
    end

    state_city_entry
  end

  def get_city_directory_path(state, city_entry)
    state_directory_file = PathHelper.project_path(File.join("data", "us", state, "places.yml"))
    state_directory = YAML.load(File.read(state_directory_file))

    city_name = city_entry["name"]

    if state_directory["places"].select { |p| p["name"] == city_name }.count > 1
      puts "❌ Multiple cities found with the same name, adding a suffix to the city path"
      city_name = "#{city_name}_#{city_entry["gnis"]}"
    end

    PathHelper.project_path(File.join("data", "us", state, city_name))
  end

  def get_city_directory_file(state, state_city_entry)
    city_directory_path = get_city_directory_path(state, state_city_entry)
    File.join(city_directory_path, "directory.yml")
  end

  def prepare_directories(state, state_city_entry)
    city_directory = get_city_directory_path(state, state_city_entry)
    cache_destination_dir = File.join(city_directory, "cache")

    FileUtils.mkdir_p(cache_destination_dir)
    FileUtils.rm_rf(File.join(city_directory, "city_scrape_sources"))

    cache_destination_dir
  end

  def fetch_content(data_fetcher, url, candidate_dir)
    data_fetcher.extract_content(url, candidate_dir)
  rescue StandardError => e
    puts "Error fetch_content: #{e.message}"
    puts "Error backtrace: #{e.backtrace.join("\n")}"
    nil
  end

  def extract_city_info(openai_service, content_file, url)
    updated_city_info = openai_service.extract_city_info(content_file, url)

    if updated_city_info.is_a?(Hash) && updated_city_info.key?("error")
      nil
    else
      updated_city_info["council_url_site"] = url
      updated_city_info
    end
  end

  def update_city_directory(
    state,
    city_entry,
    new_city_directory,
    source_dirs
  )
    update_state_places(state, [{"gnis" => city_entry["gnis"], "last_city_scrape_run" => Time.now.strftime("%Y-%m-%d")}])
    city_directory_path = get_city_directory_path(state, city_entry)
    sources_destination_dir = File.join(city_directory_path, "city_scrape_sources")
    FileUtils.mkdir_p(sources_destination_dir)

    images_dir = File.join(city_directory_path, "images")
    FileUtils.mkdir_p(images_dir)

    source_dirs.each do |source_dir|
      # store images in combined images directory
      puts "Copying images from #{source_dir}/images/* to #{images_dir}"
      Dir.glob("#{source_dir}/images/*").each do |image|
        FileUtils.cp(image, images_dir)
      end

      FileUtils.mv(source_dir, sources_destination_dir)
    end

    city_info_file = get_city_directory_file(state, city_entry)

    File.write(city_info_file, new_city_directory.to_yaml)
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

  def fetch_search_results(engine, state_city_entry, existing_urls)
    new_results = get_candidate_city_directory_urls(engine, state_city_entry)

    # Get unique results
    new_results = new_results.reject { |url| existing_urls.include?(url) }

    puts "Search engine #{engine} found #{new_results.count} new urls"
    puts new_results.join("\n")

    new_results
  end

  def process_search_results(
    engine,
    search_result_urls,
    openai_service,
    city_directory,
    source_dirs,
    cache_directory
  )
    search_pointer = 0

    data_fetcher = Scrapers::DataFetcher.new

    while search_pointer < search_result_urls.count
      url = search_result_urls[search_pointer]
      search_pointer += 1
      candidate_name = "#{engine}_#{search_pointer}"

      puts "Fetching #{url}"
      candidate_dir = prepare_candidate_dir(cache_directory, candidate_name)
      content_file = fetch_content(data_fetcher, url, candidate_dir)

      next unless content_file

      page_city_info = extract_city_info(openai_service, content_file, url)

      next unless page_city_info && page_city_info["people"].present?

      source_dirs << candidate_dir

      city_directory = refresh_city_directory(city_directory, page_city_info, url)

      council_member_count = city_directory["people"].select do |person|
        person["position"] == "council_member"
      end.count
      city_leader_count = city_directory["people"].select do |person|
        %w[mayor].include?(person["position"])
      end.count

      puts "council_member_count: #{council_member_count}, city_leader_count: #{city_leader_count}"
      return [true, source_dirs, city_directory] if council_member_count > 1 && city_leader_count.positive?

    end

    [false, source_dirs, city_directory]
  end

  def refresh_city_directory(city_directory, page_city_info, url)
    new_people = people_with_names(page_city_info["people"])
    return unless new_people.present?

    city_directory["people"] = merge_people_lists(city_directory["people"], new_people)
    city_directory["sources"] << url

    city_directory
  end

  def finalize_city_directory(state, state_city_entry, new_city_directory, source_dirs)
    city_directory_path = get_city_directory_path(state, state_city_entry)
    cache_directory = File.join(city_directory_path, "cache")

    if new_city_directory["people"].length > 1
      new_city_directory["people"] = sort_people(new_city_directory["people"])
      update_city_directory(state, state_city_entry, new_city_directory, source_dirs)
      directory_path = get_city_directory_file(state, state_city_entry)
      FileUtils.rm_rf(cache_directory)

      puts "✅ Successfully extracted city info"
      puts "Data saved to: #{directory_path}"
      exit 0 # Exit if successful
    else
      puts "❌ Error: No valid city info extracted"
      exit 1
    end
  end

  def sort_people(people)
    # sort by position - mayor first, then council_president, then council_member
    # if there is no position, then sort by position_misc alphabetically, then name
    # position and position_misc are optional, so we need to handle nil values
    position_order = {
      "mayor" => 0,
      "council_president" => 1,
      "council_member" => 2
    }
    people.sort_by do |person|
      [
        position_order[person["position"]] || Float::INFINITY,
        person["position_misc"].to_s.downcase.gsub(/[ .]+/, "_") || "",
        person["name"]
      ]
    end
  end

  def validate_pick_cities(state, num_cities)
    if state.blank? || num_cities.blank?
      puts "Error: Missing required parameters"
      puts "Usage: rake 'city_info:pick_cities[state,num_cities]'"
      puts "Example: rake 'city_info:pick_cities[wa,10]'"
      exit 1
    end
  end
end
