module CityScrape
  class StateManager
    def self.get_state_path(state)
      PathHelper.project_path(File.join("data", state))
    end

    # each places must have a gnis key
    def self.get_state_places_file(state)
      PathHelper.project_path(File.join("data_source", state, "places.json"))
    end

    def self.get_state_places(state)
      state_places_file = get_state_places_file(state)
      JSON.parse(File.read(state_places_file)) if File.exist?(state_places_file)
    end

    def self.update_state_places(state, updated_places)
      state_places = { # scaffold just in case it doesn't exist
        "ocd_id" => "ocd-division/country:us/state:#{state}",
        "places" => []
      }

      state_places_file = get_state_places_file(state)
      state_places = JSON.parse(File.read(state_places_file)) if File.exist?(state_places_file)

      updated_places.each do |updated_place|
        next unless updated_place["gnis"].present?

        existing_place_index = state_places["places"].find_index { |p| p["gnis"] == updated_place["gnis"] }
        if existing_place_index
          existing_place = state_places["places"][existing_place_index]

          merged = existing_place.merge(updated_place) do |_key, old_val, new_val|
            new_val.present? ? new_val.dup : old_val.dup
          end
          state_places["places"][existing_place_index] = merged
        else
          state_places["places"] << updated_place
        end
      end

      File.write(state_places_file, JSON.pretty_generate(state_places))
    end

    def self.get_city_entry_by_gnis(state, gnis)
      state_places = get_state_places(state)
      state_places["places"].find { |place| place["gnis"] == gnis }
    end
  end
end
