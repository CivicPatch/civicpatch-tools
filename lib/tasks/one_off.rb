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

  task :fix_meta_sources do
    state = "wa"
    municipalities = CityScrape::StateManager.get_state_places(state)["places"]
    municipalities_to_update = municipalities.map do |municipality|
      next nil if municipality["meta_sources"].present?

      people = Core::PeopleManager.get_people(state, municipality["gnis"])
      next nil if people.empty?

      puts "Updating #{municipality["name"]} with gnis #{municipality["gnis"]}"
      {
        "gnis" => municipality["gnis"],
        "meta_sources" => %w[state_source gemini openai]
      }
    end.compact

    puts "Updating #{municipalities_to_update.size} municipalities"
    CityScrape::StateManager.update_state_places(state, municipalities_to_update)
  end
end
