require "services/spaces"

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
    images = Dir.glob("data/**/**/images/*")

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
end
