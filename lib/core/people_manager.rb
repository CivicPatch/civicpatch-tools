require "zaru"

module Core
  class PeopleManager
    POSITION_ORDER = {
      "Mayor" => 0,
      "Council President" => 1,
      "Council Manager" => 2,
      "Council Member" => 3
    }.freeze

    def self.get_position_order(government_type)
      # sort by list of positions
      # then by divisions
      # then alphabetically
    end

    def self.merge_person(person1, person2)
      merged_person = {}

      # Define merging rules for each field
      person1.each do |field, value|
        case field
        when "name"
          # Keep name from the first person (person1)
          merged_person["name"] = value
        when "image"
          merged_person["image"] = person2["image"] || value
        when "positions"
          merged_person["positions"] = (Array(value) + Array(person2["positions"])).uniq
        when "email"
          merged_person["email"] = person2["email"] || value
        when "phone_number"
          merged_person["phone_number"] = person2["phone_number"] || value
        when "website"
          merged_person["website"] = person2["website"] || value
        when "sources"
          sources = (Array(value) + Array(person2["sources"])).uniq
          merged_person["sources"] = sources
        end
      end

      # Handle fields that are in person2 but not in person1
      person2.each do |field, value|
        merged_person[field] ||= value
      end

      merged_person
    end

    def self.merge_people(city_directory, partial_city_directory)
      new_people = people_with_names(partial_city_directory)
      return city_directory unless new_people.present?

      sort_people(merge_people_lists(city_directory, new_people))
    end

    def self.merge_people_lists(list1, list2)
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
          combined_person = merge_person(person1, match_person)
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

    def self.valid_city_people?(people)
      council_members = get_council_members_count(people)
      mayors = get_mayors_count(people)

      council_members > 1 && mayors.positive?
    end

    # TODO: needs config-driven
    def self.get_council_members_count(people)
      people.select do |person|
        person["positions"].include?("Council Member")
      end.count
    end

    def self.get_mayors_count(people)
      people.select do |person|
        person["positions"].include?("Mayor")
      end.count
    end

    def self.update_people(
      state,
      city_entry,
      new_city_people,
      directory_type = nil
    )
      if directory_type.present?
        city_people_path = PathHelper.get_city_people_candidates_file_path(state, city_entry["gnis"],
                                                                           directory_type)
      else
        city_people_path = get_city_directory_file(state, city_entry)
        raise "Invalid city people path: #{city_people_path}" unless city_people_path.present?
      end

      File.write(city_people_path, new_city_people.to_yaml)
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

    def self.people_with_names(people)
      people.select { |person| person["name"].present? }
    end
  end
end
