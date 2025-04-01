require_relative "./city_scrape/city_manager"

namespace :validate do
  desc "Validate city directory against an official source"
  task :city_directory, [:state, :gnis] do |_t, args|
    state = args[:state]
    gnis = args[:gnis]

    city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
  end
end
