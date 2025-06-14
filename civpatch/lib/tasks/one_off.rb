# frozen_string_literal: true

require "services/spaces"
require "utils/folder_helper"
require "core/config_manager"
require "scrapers/municipalities"

namespace :one_off do
  task "count_municipalities" do
    state = "nh"
    municipalities = Core::StateManager.get_municipalities(state)["municipalities"]
    puts municipalities.length

    puts "diff from census?"

    census_municipalities = File.read(Core::PathHelper.project_path(File.join("data", state, ".maps",
                                                                              "municipalities.geojson")))
    census_map = JSON.parse(census_municipalities)
    census_features = census_map["features"]

    municipalities.each do |municipality|
      has_entry = census_features.any? { |feature| feature["properties"]["geoid"] == municipality["geoid"] }

      puts "Could not find municipality: #{municipality["name"]} - #{municipality["geoid"]}" unless has_entry
    end

    puts "Municipalities: #{municipalities.length} features..."
    puts "Census: #{census_features.length} features..."

    puts "Diff: #{census_features.length - municipalities.length} features..."
  end

  task "cleanup_wa" do
    state = "wa"
    municipalities = File.read(Core::PathHelper.project_path(File.join("data_source", state, "municipalities.json")))
    munic_json = JSON.parse(municipalities)
    munic = munic_json["municipalities"]
    munic.each do |municipality|
      next unless municipality["geoid"].blank?

      found_dupe = munic.find do |m|
        m["name"].capitalize == municipality["name"].capitalize && m["geoid"].present?
      end

      if found_dupe
        puts "Found dupe: #{found_dupe["name"]} - #{found_dupe["geoid"]}"
        munic.delete(municipality)
      else
        puts "No dupe found: #{municipality["name"]} - #{municipality["geoid"]}" unless municipality["geoid"].present?
      end
    end

    munic_json["municipalities"] = munic

    File.write(Core::PathHelper.project_path(File.join("data_source", state, "municipalities.json")),
               JSON.pretty_generate(munic_json))
  end

  desc "Scrape city offficials from a state-level source"
  task :fetch_from_state_source, [:state] do |_t, args|
    state = args[:state]
    government_type = Core::CityManager::GOVERNMENT_TYPE_MAYOR_COUNCIL

    municipalities = Core::StateManager.get_state_places(state)["places"]
    filtered_municipalities = municipalities.select do |m|
      people = Core::PeopleManager.get_people(state, m["gnis"])
      people.empty?
    end

    filtered_municipalities.each do |municipality|
      fetch_with_source(state, municipality, government_type)
      aggregate_sources(state, municipality, government_type, sources: %w[state_source])
    end
  end

  desc "Add NH census geoid"
  task :fix_nh do
    state = "nh"
    municipalities = Scrapers::Municipalities.fetch(state)
    Core::StateManager.update_municipalities(state, municipalities)
  end

  task :get_gov_types do
    state = "nh"
    municipalities = Core::StateManager.get_municipalities(state)["municipalities"]
    government_types_by_count = {}
    government_types_with_no_government_type = []
    government_types_town_manager = []
    municipalities.each do |municipality|
      if municipality["government_type"].blank?
        government_types_with_no_government_type << municipality
      else
        government_types_by_count[municipality["government_type"]] =
          government_types_by_count[municipality["government_type"]].to_i + 1
      end

      government_types_town_manager << municipality if municipality["government_type"] == "town manager"
    end

    # ~puts government_types_by_count.sort_by { |_key, value| value }.reverse
    # ~puts(government_types_with_no_government_type.map { |municipality| municipality["name"] })
    puts(government_types_town_manager.map { |municipality| municipality["name"] })
  end

  task :test_source do
    state = "wa"
    municipalities = Core::StateManager.get_state_places(state)["places"]
    municipality_entry = municipalities.first
    puts municipality_entry

    government_type = Core::CityManager::GOVERNMENT_TYPE_MAYOR_COUNCIL
    positions_config = Core::CityManager.get_positions(government_type)
    source_city_people = Scrapers::LocalOfficialScraper.fetch_with_state_source(state, municipality_entry)
    Core::PeopleManager.update_people(state, municipality_entry, source_city_people, "state_source.before")
    formatted_source_city_people = Core::PeopleManager.format_people(source_city_people, positions_config)
    Core::PeopleManager.update_people(state, municipality_entry, formatted_source_city_people, "state_source.after")

    # updated_city = {
    #  "gnis" => city_entry["gnis"],
    #  "meta_sources" => %w[state_source gemini openai]
    # }

    # CityScrape::StateManager.update_state_places(state, [updated_city])
  end

  task :view_comparison do
    state = "wa"
    gnis = "2411856"
    results = Validators::CityPeople.validate_sources(state, gnis)
    pp results
  end

  task :move_images_to_spaces do
    # Get all images under data/<state>/<cities>/images
    # MIME_TYPE_MAPPINGS = {
    #  "png" => "image/png",
    #  "jpg" => "image/jpeg",
    #  "jpeg" => "image/jpeg",
    #  "gif" => "image/gif",
    #  "webp" => "image/webp"
    # }
    Dir.glob("data/**/**/images/*")

    # images.each do |image_path|
    #  puts image_path
    #  File.delete(image_path)
    #  directory = File.dirname(image_path)
    #  FileUtils.rm_rf(directory) if directory.empty?
    #  # key = image_path.gsub("data/", "")
    #  # file_extension = File.extname(key)
    #  # content_type = MIME_TYPE_MAPPINGS[file_extension.delete(".")]
    #  # Services::Spaces.put_object(key, image_path, content_type)
    # end

    # image_dirs = Dir.glob("data/**/**/images")
    # image_dirs.each do |image_dir|
    #  puts image_dir
    #  FileUtils.rm_rf(image_dir) if image_dir.empty?
    # end

    ## Delete the images directory and all files under it
    # path = PathHelper.project_path("data/**/**/images")
    # puts "Deleting #{path}"
    # FileUtils.rm_rf(path)

    # Update image refs
    # Get all files under data/<state>/<cities>/people.yml
    people_files = Dir.glob("data/**/**/people.yml")
    people_files.each do |people_file|
      city_path = people_file.gsub("data/", "").gsub("/people.yml", "")
      people = YAML.load_file(people_file)
      fixed_people = people.map do |person|
        next person if person["image"].blank?

        image_key = "#{city_path}/#{person["image"]}"
        person["image"] = "https://cdn.civicpatch.org/open-data/#{image_key}"
        person
      end

      File.write(people_file, fixed_people.to_yaml)
    end
  end

  task :sort_by_population do
    # Get all files under data/<state>/<cities>/people.yml
    file_path = PathHelper.project_path("data_source/or/municipalities.json")
    municipalities = JSON.parse(File.read(file_path))
    descending = -1
    updated_municipalities = municipalities["municipalities"].sort_by do |municipality|
      municipality["population"] * descending
    end
    municipalities["municipalities"] = updated_municipalities
    File.write(file_path, JSON.pretty_generate(municipalities))
  end

  task :fix_or_casings do
    # Get all directories under data/or/<cities>
    folders = Dir.glob("data/or/*")
    folders.each do |folder|
      # Get the name of the folder
      name = folder.split("/").last
      # Format the name
      formatted_name = Utils::FolderHelper.format_name(name)
      # Rename the folder
      system("git mv #{folder} #{folder}2")
      system("git mv #{folder}2 data/or/#{formatted_name}")
    end
  end

  task :test_gemini_search do
    state = "mi"
    municipality_context = {
      state: state,
      municipality_entry: {
        "name" => "Buchanan",
        "website" => "https://www.cityofbuchanan.com"
      }
    }
    google_gemini = Services::GoogleGemini.new
    response = google_gemini.search_for_candidate_urls(municipality_context)
    puts response
  end

  task :suggest_edit do
    state = "wa"
    municipality_entry = Core::StateManager.get_city_entry_by_gnis(state, "2410494")
    Scrapers::Wa::MunicipalityOfficials::StateLevelScraper.get_suggest_edit_details(municipality_entry)
  end

  task :weak_ties do
    state = "or"
    municipality_entry = Core::StateManager.get_city_entry_by_gnis(state, "2411332")
    config = Core::ConfigManager.get_config(state, municipality_entry["gnis"])
    municipality_context = {
      state: state,
      municipality_entry: municipality_entry,
      config: config
    }

    results = Validators::CityPeople.validate_sources(municipality_context)
    pp results
  end

  task :remove_all_state_source_files do
    # Get all files under data/<state>/<cities>/people.yml
    file_path = "data_source/wa/**/people/people_state_source.*.json"
    Dir.glob(file_path).each do |file|
      File.delete(file)
    end
  end

  task :google_gemini_search do
    state = "or"
    municipality_entry = Core::StateManager.get_city_entry_by_gnis(state, "2412103")
    config = Core::ConfigManager.get_config(state, municipality_entry["gnis"])
    municipality_context = {
      state: state,
      municipality_entry: municipality_entry,
      config: config
    }

    google_gemini = Services::GoogleGemini.new
    response = google_gemini.search_for_people(municipality_context)
    pp response
  end

  task :to_csv do
    # Get all files under data/<state>/<cities>/people.yml
    states_to_name = {
      "wa" => "Washington",
      "or" => "Oregon"
    }
    file_path = "data/**/people.yml"
    csv_file_path = "data/people.csv"
    csv_file = File.open(csv_file_path, "w")
    csv_file.puts %w[state_name state_abbrev city_name name positions image source_image email
                     phone_number website start_date end_date].join(",")
    Dir.glob(file_path).each do |file|
      # find state from data/<state>/<cities>/people.yml
      state_abbrev = file.split("/").second
      state_name = states_to_name[state_abbrev]
      city_name = file.split("/").third
      people = YAML.load_file(file)
      people.each do |person|
        csv_file.puts [state_name, state_abbrev, city_name, person["name"], person["roles"].join("|"), person["image"], person["cdn_pameg"],
                       person["email"], person["phone_number"], person["website"], person["start_date"], person["end_date"]].join(",")
      end
    end
    csv_file.close
  end

  task :scrape_nh do
    Scrapers::Municipalities.fetch("nh")
  end

  task :count_mun do
    state = "wa"
    municipalities = Core::StateManager.get_municipalities(state)["municipalities"]
    puts municipalities.select { |municipality| municipality["website"].present? }.length
  end

  task :update_government_types do
    official_government_types = %w[mayor_council selectmen aldermen town_meeting]
    state = "wa"
    municipalities = Core::StateManager.get_municipalities(state)["municipalities"]
    municipalities.map do |municipality|
      next municipality if official_government_types.include?(municipality["government_type"])
      next municipality if municipality["government_type"].nil?

      new_government_type = to_government_type(municipality["government_type"])
      puts "Could not find government type for #{municipality["government_type"]}" if new_government_type.nil?
      next municipality if new_government_type.nil?

      municipality["government_type"] = new_government_type
      municipality
    end

    Core::StateManager.update_municipalities(state, municipalities)
  end

  task :rerun_for_non_roles do
    state = "nh"
    municipalities_core = Core::StateManager.get_municipalities(state)
    municipalities = municipalities_core["municipalities"]
    updated_municipalities = municipalities.map do |municipality|
      next municipality if (municipality["meta_sources"]&.length || 0) < 3

      people = Core::PeopleManager.get_people(state, municipality["geoid"])

      if people.any? { |person| person["roles"].blank? }
        puts "#{municipality["name"]} - #{municipality["geoid"]} - needs to be rerun"
        municipality["meta_sources"] = []
        next municipality
      else
        puts "Skipping #{municipality["name"]} - #{municipality["geoid"]}"
        next municipality
      end
    end

    municipalities_core["municipalities"] = updated_municipalities
    File.write(Core::PathHelper.project_path(File.join("data_source", state, "municipalities.json")),
               JSON.pretty_generate(municipalities_core))
  end

  task :remove_cached_files do
    remove_cached_files
  end

  def self.to_government_type(raw_government_type_string)
    government_type = nil
    formatted_raw_government_type_string = raw_government_type_string.downcase
    if formatted_raw_government_type_string.include?("council")
      government_type = "mayor_council"
    elsif formatted_raw_government_type_string.include?("select")
      government_type = "selectmen"
    elsif formatted_raw_government_type_string.include?("alder")
      government_type = "aldermen"
    elsif formatted_raw_government_type_string.include?("town") && formatted_raw_government_type_string.include?("meeting")
      government_type = "town_meeting"
    end

    government_type
  end

  def self.format_name(name)
    # Split the name by space separated by _
    # Capitalize the first letter of each word
    # Join the words back together
    name.split("_").map(&:capitalize).join(" ")
  end

  def self.remove_cached_files
    file_path = "data_source/**/cache/**/*"
    Dir.glob(file_path).each do |file|
      next if File.directory?(file)

      puts "Deleting #{file}"
      File.delete(file) unless file.end_with?(".md")
    end
  end
end
