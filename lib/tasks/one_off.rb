namespace :one_off do
  desc "Scrape city offficials from a state-level source"
  task :fetch_from_state_source, [:state] do |_t, args|
    state = args[:state]
    government_type = Core::CityManager::GOVERNMENT_TYPE_MAYOR_COUNCIL

    municipalities = CityScrape::StateManager.get_state_places(state)["places"]
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
    municipalities = CityScrape::StateManager.get_state_places(state)["places"]
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
end
