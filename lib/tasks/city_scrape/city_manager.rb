module CityScrape
  class CityManager
    # sort by position - mayor first, then council_president, then council_member
    # if there is no position, then sort by position_misc alphabetically, then name
    # position and position_misc are optional, so we need to handle nil values
    POSITION_ORDER = {
      "mayor" => 0,
      "council_president" => 1,
      "council_member" => 2
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
      "common" => ["index", "government"]
    }.freeze

    # Might want to add more checks here
    def self.includes_people?(directory)
      directory["people"].present? && directory["people"].count > 1
    end

    def self.valid_city_directory?(directory)
      council_members = directory["people"].count { |person| person["position"] == "council_member" }
      mayors = directory["people"].count { |person| person["position"] == "mayor" }

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
        [
          POSITION_ORDER[person["position"]] || Float::INFINITY,
          format_position_title(person["position_misc"]),
          person["name"]
        ]
      end
    end

    def self.merge_directory(city_directory, partial_city_directory, url)
      new_people = CityScrape::CityManager.people_with_names(partial_city_directory["people"])
      return city_directory unless new_people.present?

      {
        "people" => sort_people(merge_people_lists(city_directory["people"], new_people)),
        "sources" => city_directory["sources"] + [url]
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
      list2.each do |person|
        name_key = full_name.call(person)
        if people_hash[name_key]
          # Merge properties if the person already exists, prefer properties from the first list unless the first list is empty
          people_hash[name_key].merge!(person) do |_key, old_val, new_val|
            if old_val.is_a?(Array) && new_val.is_a?(Array)
              (old_val + new_val).uniq
            else
              old_val.present? ? old_val : new_val
            end
          end
        else
          people_hash[name_key] = person.dup
        end
      end

      # Convert the hash back to an array
      people_hash.values
    end
  end
end
