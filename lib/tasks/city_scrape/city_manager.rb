module CityScrape
  class CityManager
    # sort by position - mayor first, then council_president, then council_member
    # if there is no position, then sort by position_misc alphabetically, then name
    # position and position_misc are optional, so we need to handle nil values
    POSITION_ORDER = {
      "Mayor" => 0,
      "Council President" => 1,
      "Council Manager" => 2,
      "Council Member" => 3
    }.freeze

    KEYWORD_GROUPS = {
      "council_members" => ["mayor and city council",
                            "meet the council",
                            "city council members",
                            "council districts",
                            "council members",
                            "councilmembers",
                            "city council",
                            "council"],
      "city_leaders" => ["meet the mayor",
                         "about the mayor",
                         "mayor",
                         "council president"],
      "common" => %w[index government]
    }.freeze

    MERGE_RULES = {
      "name" => { type: "FIRST" },
      "image" => { type: "LAST" },
      "contact_details" => { type: "MERGE", value: "value" },
      "links" => { type: "MERGE", value: "url" },
      "other_names" => {
        type: "MERGE",
        value: "name",
        sort_by: ->(other_names) { sort_by_positions(other_names) }
      },
      "updated_at" => { type: "LAST" },
      "created_at" => { type: "LAST" },
      "sources" => { type: "MERGE", value: "url" }
    }.freeze

    def self.sort_by_positions(other_names)
      other_names.sort_by do |other_name|
        position = other_name["name"]
        order = POSITION_ORDER[position] || Float::INFINITY
        [order, position]
      end
    end

    # Might want to add more checks here
    def self.includes_people?(directory)
      directory["people"].present? && directory["people"].any?
    end

    def self.valid_city_directory?(directory)
      person_other_names = directory["people"].map do |person|
        (person["other_names"] || []).map do |other_name|
          other_name["name"]
        end
      end.flatten

      council_members = person_other_names.select { |other_name| other_name.include?("Council Member") }.count
      mayors = person_other_names.select { |other_name| other_name.include?("Mayor") }.count

      puts "Council members: #{council_members}, Mayors: #{mayors}"

      council_members > 1 && mayors.positive?
    end

    def self.people_with_names(people)
      people.select { |person| person["name"].present? }
    end

    def self.format_position_title(position_title)
      (position_title || "").to_s.downcase.gsub(/[ .]+/, "_")
    end

    def self.update_city_directory(
      state,
      city_entry,
      new_city_directory
    )
      city_directory_path = get_city_directory_file(state, city_entry)
      raise "Invalid city directory path: #{city_directory_path}" unless city_directory_path.present?

      File.write(city_directory_path, new_city_directory.to_yaml)
    end

    def self.get_city_path(state, city_entry)
      state_path = CityScrape::StateManager.get_state_path(state)
      city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, city_entry["gnis"])
      state_places = CityScrape::StateManager.get_state_places(state)

      path_name = city_entry["name"]

      # Some cities within the same state have the same name
      if state_places["places"].count { |place| place["name"] == city_entry["name"] } > 1
        path_name = "#{city_entry["name"]}_#{city_entry["gnis"]}"
      end

      File.join(state_path, path_name)
    end

    def self.get_city_directory_file(state, city_entry)
      File.join(get_city_path(state, city_entry), "directory.yml")
    end

    def self.get_city_directory(state, city_entry)
      city_directory_path = get_city_directory_file(state, city_entry)
      raise "Invalid city directory path: #{city_directory_path}" unless city_directory_path.present?

      YAML.load(File.read(city_directory_path))
    end

    def self.sort_people(people)
      people.sort_by do |person|
        position = person["other_names"]&.first&.dig("name")

        [
          POSITION_ORDER[position] || Float::INFINITY,
          person["name"].to_s # fallback to name for ties
        ]
      end
    end

    def self.merge_directory(city_directory, partial_city_directory)
      new_people = CityScrape::CityManager.people_with_names(partial_city_directory["people"])
      return city_directory unless new_people.present?

      {
        "people" => sort_people(merge_people_lists(city_directory["people"], new_people))
      }
    end

    def self.merge_people_lists(list1, list2)
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
      list2.each do |updated_person|
        name_key = full_name.call(updated_person)
        # Use MERGE_RULES to determine how to merge the properties
        existing_person = people_hash[name_key]
        if existing_person.nil?
          people_hash[name_key] = updated_person
          next
        end

        people_hash[name_key] = merge_person(existing_person, updated_person)
      end

      # Convert the hash back to an array
      people_hash.values
    end

    def self.merge_person(existing_person, updated_person)
      merged_person = existing_person.dup
      updated_person.each_key do |key|
        rule = MERGE_RULES[key] || { type: "FIRST" }

        merged_person[key] = if updated_person[key].is_a?(Array)
                               puts "updated_person: #{updated_person[key].inspect}"
                               puts "missing key: #{key}"
                               unique_field = MERGE_RULES[key][:value]
                               # Merge arrays, key only unique values by the indicated field
                               merged_array = (existing_person[key] + updated_person[key]).uniq do |item|
                                 item[unique_field]
                               end

                               merged_array = rule[:sort_by].call(merged_array) if rule[:sort_by]
                               merged_array
                             else
                               case rule[:type]
                               when "FIRST" # Keep old value unless it's nil
                                 existing_person[key] || updated_person[key]
                               when "LAST" # Keep new value unless it's nil
                                 updated_person[key] || existing_person[key]
                               else
                                 updated_person[key] || existing_person[key]
                               end
                             end
      end

      merged_person
    end
  end
end
