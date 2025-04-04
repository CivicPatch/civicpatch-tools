require "fuzzy_match"

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

    def custom_merge(person1, person2)
      merged_person = {}

      # Define merging rules for each field
      person1.each do |field, value|
        case field
        when "name"
          # Keep name from the first person (person1)
          merged_person["name"] = value
        when "image"
          # Average the age if different
          merged_person["image"] = person2["image"]
        when "positions"
          # Combine the address fields
          merged_person["positions"] = [value, person2["positions"]].compact.join(", ")
        when "email"
          # Default merging behavior: prefer the last person's value
          merged_person["email"] = person2["email"]
        when "phone_number"
          # Default merging behavior: prefer the last person's value
          merged_person["phone_number"] = person2["phone_number"]
        when "website"
          # Default merging behavior: prefer the last person's value
          merged_person["website"] = person2["website"]
        when "sources"
          # Default merging behavior: prefer the last person's value
          merged_person["sources"] = person2["sources"]
        end
      end

      # Handle fields that are in person2 but not in person1
      person2.each do |field, value|
        merged_person[field] ||= value
      end

      merged_person
    end

    def self.sort_by_positions(other_names)
      other_names.sort_by do |other_name|
        position = other_name["name"]
        order = POSITION_ORDER[position] || Float::INFINITY
        [order, position]
      end
    end

    # Might want to add more checks here
    def self.includes_people?(directory)
      directory.present? && directory.any?
    end

    def self.valid_city_directory?(directory)
      council_members = get_council_members_count(directory)
      mayors = get_mayors_count(directory)

      council_members > 1 && mayors.positive?
    end

    def self.get_council_members_count(directory)
      directory.select do |person|
        person["positions"].include?("Council Member")
      end.count
    end

    def self.get_mayors_count(directory)
      directory.select do |person|
        person["positions"].include?("Mayor")
      end.count
    end

    def self.people_with_names(people)
      people.select { |person| person["name"].present? }
    end

    def self.format_position_title(position_title)
      (position_title || "").to_s.downcase.gsub(/[ .]+/, "_")
    end

    def self.update_directory(
      state,
      city_entry,
      new_city_directory,
      directory_type = nil
    )
      if directory_type.present?
        city_directory_path = PathHelper.get_city_directory_candidates_file_path(state, city_entry["gnis"],
                                                                                 directory_type)
      else
        city_directory_path = get_city_directory_file(state, city_entry)
        raise "Invalid city directory path: #{city_directory_path}" unless city_directory_path.present?
      end

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
      new_people = CityScrape::CityManager.people_with_names(partial_city_directory)
      return city_directory unless new_people.present?

      sort_people(merge_people_lists(city_directory, new_people))
    end

    def self.merge_people_lists(list1, list2)
      # Combine by exact name match

      # Initialize fuzzy matcher
      fuzzy_matcher = FuzzyMatch.new(list2.map { |p| p[:name] })

      # Combine lists using fuzzy matching
      combined_list = []

      list1.each do |person1|
        match_name = fuzzy_matcher.find(person1[:name])

        if match_name
          # Find the matched person from list2
          match_person = list2.find { |p| p[:name] == match_name }

          # Merge the matched person (you can customize this logic)
          combined_person = custom_merge(person1, match_person)
          combined_list << combined_person

          # Remove the matched person from list2 to avoid duplicates
          list2.delete(match_person)
        else
          combined_list << person1
        end
      end

      # Add remaining unmatched people from list2
      combined_list.concat(list2)
    end

    def self.merge_person(existing_person, updated_person)
      merged_person = existing_person.dup
      updated_person.each_key do |key|
        rule = MERGE_RULES[key] || { type: "FIRST" }

        merged_person[key] = if updated_person[key].is_a?(Array)
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
