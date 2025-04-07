require "zaru"
require "amatch"
require_relative "./person_manager/utils"

module Core
  class PeopleManager
    def self.get_people(state, gnis, type)
      people_file_path = PathHelper.get_city_people_candidates_file_path(state, gnis, type)
      YAML.load(File.read(people_file_path))
    end

    def self.normalize_people(people, positions_config)
      people.each do |person|
        person["positions"] = Core::PersonManager::Utils
                              .sort_positions(person["positions"], positions_config)
      end

      people
    end

    # Without extra positions
    def self.format_people(people, positions_config)
      people.each do |person|
        person["name"] = person["name"].squeeze(" ")
        person["positions"] = Core::PersonManager::Utils
                              .sort_positions(person["positions"], positions_config)
                              .map do |position|
                                Core::PersonManager::Utils
                                  .format_position(position)
                              end
      end

      filtered_people = people.reject { |person| person["positions"].count.zero? }
      Core::PersonManager::Utils.sort_people(filtered_people, positions_config)
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

      merge_people_lists(city_directory, new_people)
    end

    def self.merge_people_lists(list1, list2, threshold = 0.8)
      matcher = FuzzyMatch.new(list1.map { |person| person["name"] })

      # Make a copy of list1 to avoid modifying the original list
      merged = list1.dup

      list2.each do |person2|
        matched_name = find_match(person2["name"], list1, matcher, threshold)

        if matched_name
          # Find the matched person from list1
          matched_person = list1.find { |person| person["name"] == matched_name }

          # If the matched person is found in list1, merge them
          if matched_person
            index = merged.index { |person| person["name"] == matched_person["name"] }
            merged[index] = merge_person(merged[index], person2)
          end
        else
          merged << person2
        end
      end

      merged
    end

    def self.find_match(name, list, matcher, threshold)
      best_match = matcher.find(name)
      return nil unless best_match

      similarity = best_match.pair_distance_similar(name)
      similarity >= threshold ? list.find { |p| p["name"] == best_match } : nil
    end

    def self.valid_city_people?(people)
      council_members = get_council_members_count(people)
      mayors = get_mayors_count(people)

      council_members > 1 && mayors.positive?
    end

    # TODO: needs config-driven
    def self.get_council_members_count(people)
      people.select do |person|
        person["positions"].map(&:downcase).include?("council member")
      end.count
    end

    def self.get_mayors_count(people)
      people.select do |person|
        person["positions"].map(&:downcase).include?("mayor")
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
        city_people_path = File.join(PathHelper.get_city_path(state, city_entry["gnis"]), "people.yml")
        raise "Invalid city people path: #{city_people_path}" unless city_people_path.present?
      end

      File.write(city_people_path, new_city_people.to_yaml)
    end

    def self.people_with_names(people)
      people.select { |person| person["name"].present? }
    end
  end
end
