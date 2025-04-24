module CityScrape
  class StateManager
    def self.get_state_path(state)
      PathHelper.project_path(File.join("data", state))
    end

    # each places must have a gnis key
    def self.get_state_municipalities_file(state)
      PathHelper.project_path(File.join("data_source", state, "municipalities.json"))
    end

    # TODO: fix broken get_state_places
    def self.get_state_municipalities(state)
      state_municipalities_file = get_state_municipalities_file(state)
      JSON.parse(File.read(state_municipalities_file)) if File.exist?(state_municipalities_file)
    end

    def self.update_state_municipalities(state, updated_municipalities)
      state_municipalities = { # scaffold just in case it doesn't exist
        "ocd_id" => "ocd-division/country:us/state:#{state}",
        "municipalities" => []
      }

      state_municipalities_file = get_state_municipalities_file(state)

      if File.exist?(state_municipalities_file)
        state_municipalities = JSON.parse(File.read(state_municipalities_file))
      else
        FileUtils.mkdir_p(File.dirname(state_municipalities_file))
        File.write(state_municipalities_file, JSON.pretty_generate(state_municipalities))
      end

      puts "Updating #{updated_municipalities.size} municipalities for #{state}"

      updated_municipalities.each do |updated_municipality|
        next unless updated_municipality["gnis"].present?

        existing_municipality_index = state_municipalities["municipalities"].find_index do |m|
          m["gnis"] == updated_municipality["gnis"]
        end
        if existing_municipality_index
          existing_municipality = state_municipalities["municipalities"][existing_municipality_index]

          merged = existing_municipality.merge(updated_municipality) do |_key, old_val, new_val|
            new_val.present? ? new_val.dup : old_val.dup
          end
          state_municipalities["municipalities"][existing_municipality_index] = merged
        else
          state_municipalities["municipalities"] << updated_municipality
        end
      end

      File.write(state_municipalities_file, JSON.pretty_generate(state_municipalities))
    end

    def self.get_city_entry_by_gnis(state, gnis)
      state_municipalities = get_state_municipalities(state)
      state_municipalities["municipalities"].find { |municipality| municipality["gnis"] == gnis }
    end
  end
end
