# frozen_string_literal: true

require "services/spaces"
require "utils/folder_helper"
require "core/config_manager"

namespace :one_off do
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

  desc "Fix WA city names"
  task :fix_wa_city_names do
    state = "wa"
    municipalities = Core::StateManager.get_municipalities(state)["municipalities"]
    updated_municipalities = municipalities.map do |municipality|
      municipality["name"] = municipality["name"].gsub("_", " ")
      municipality
    end

    Core::StateManager.update_municipalities(state, updated_municipalities)
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
    file_path = "data_source/or/**/people/people_state_source.*.json"
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

  def self.format_name(name)
    # Split the name by space separated by _
    # Capitalize the first letter of each word
    # Join the words back together
    name.split("_").map(&:capitalize).join(" ")
  end
end
