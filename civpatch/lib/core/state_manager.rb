# frozen_string_literal: true

module Core
  class StateManager
    def self.get_state_path(state)
      Core::PathHelper.project_path(File.join("data", state))
    end

    # each places must have a geoid key
    def self.get_municipalities_file(state)
      Core::PathHelper.project_path(File.join("data_source", state, "municipalities.json"))
    end

    # TODO: fix broken get_state_places
    def self.get_municipalities(state)
      municipalities_file = get_municipalities_file(state)
      JSON.parse(File.read(municipalities_file)) if File.exist?(municipalities_file)
    end

    def self.update_municipalities(state, updated_municipalities)
      municipalities = { # scaffold just in case it doesn't exist
        "municipalities" => []
      }

      municipalities_file = get_municipalities_file(state)

      if File.exist?(municipalities_file)
        municipalities = JSON.parse(File.read(municipalities_file))
      else
        FileUtils.mkdir_p(File.dirname(municipalities_file))
        File.write(municipalities_file, JSON.pretty_generate(municipalities))
      end

      puts "Updating #{updated_municipalities.size} municipalities for #{state}"

      updated_municipalities.each do |updated_municipality|
        next unless updated_municipality["geoid"].present?

        existing_municipality_index = municipalities["municipalities"].find_index do |m|
          m["geoid"] == updated_municipality["geoid"]
        end
        if existing_municipality_index
          existing_municipality = municipalities["municipalities"][existing_municipality_index]

          merged = existing_municipality.merge(updated_municipality) do |_key, old_val, new_val|
            new_val.present? ? new_val.dup : old_val.dup
          end
          municipalities["municipalities"][existing_municipality_index] = merged
        else
          municipalities["municipalities"] << updated_municipality
        end
      end

      File.write(municipalities_file, JSON.pretty_generate(municipalities))
    end

    def self.get_city_entry_by_geoid(state, geoid)
      municipalities = get_municipalities(state)
      municipalities["municipalities"].find { |municipality| municipality["geoid"] == geoid }
    end
  end
end
