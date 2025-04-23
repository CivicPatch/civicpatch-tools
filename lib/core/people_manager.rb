require "zaru"
require "amatch"
require "utils/url_helper"
require "utils/phone_helper"
require "core/person_manager/utils"

module Core
  class PeopleManager
    def self.get_people(state, gnis, type = nil)
      if type.present?
        people_file_path = PathHelper.get_people_candidates_file_path(state, gnis, type)
        content = JSON.parse(File.read(people_file_path))
      else
        people_file_path = File.join(PathHelper.get_data_city_path(state, gnis), "people.yml")
        content = if File.exist?(people_file_path)
                    YAML.safe_load(File.read(people_file_path))
                  else
                    []
                  end
      end

      content
    end

    def self.normalize_people(people, positions_config)
      people.map do |person|
        person["positions"] = Core::PersonManager::Utils
                              .sort_positions(person["positions"], positions_config)
      end
    end

    # Without extra positions
    def self.format_people(people, positions_config)
      people.map do |person|
        person["name"] = person["name"].squeeze(" ")
        person["positions"] = Core::PersonManager::Utils
                              .sort_positions(person["positions"], positions_config)
                              .map do |position|
                                Core::PersonManager::Utils
                                  .format_position(position)
                              end

        person["website"] = Utils::UrlHelper.format_url(person["website"]) if person["website"].present?
        if person["phone_number"].present?
          person["phone_number"] =
            Utils::PhoneHelper.format_phone_number(person["phone_number"])
        end

        next person unless person["sources"].present?

        person["sources"] = person["sources"].map do |source|
          Utils::UrlHelper.format_url(source)
        end

        person
      end

      filtered_people = people.reject { |person| person["positions"].count.zero? }
      Core::PersonManager::Utils.sort_people(filtered_people, positions_config)
    end

    def self.merge_person(person1, person2)
      return person1 || person2 if person1.nil? || person2.nil?

      merged_person = {}

      # Define merging rules for each field
      person1.each do |field, value|
        case field
        when "name"
          # Keep name from the first person (person1)
          merged_person["name"] = value
        when "image"
          merged_person["image"] = person2["image"] || value
        when "source_image"
          merged_person["source_image"] = person2["source_image"] || value
        when "positions"
          merged_person["positions"] = (Array(value) + Array(person2["positions"])).uniq
        when "email"
          merged_person["email"] = person2["email"] || value
        when "phone_number"
          merged_person["phone_number"] = person2["phone_number"] || value
        when "website"
          url = person2["website"] || value
          merged_person["website"] = url
        when "sources"
          sources = (Array(value) + Array(person2["sources"])).compact.uniq
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
      positions = people.map { |p| p["positions"] }.flatten.map(&:downcase)
      positions.count { |position| position.include?("council member") }
    end

    def self.get_mayors_count(people)
      positions = people.map { |p| p["positions"] }.flatten.map(&:downcase)
      positions.count { |position| position.include?("mayor") }
    end

    def self.has_contact_info?(person)
      person["email"].present? || person["phone_number"].present? || person["website"].present?
    end

    def self.update_people(
      state,
      city_entry,
      new_city_people,
      directory_type = nil
    )
      if directory_type.present?
        city_people_path = PathHelper.get_people_candidates_file_path(state, city_entry["gnis"],
                                                                      directory_type)
        content = JSON.pretty_generate(new_city_people)
      else
        city_people_path = File.join(PathHelper.get_data_city_path(state, city_entry["gnis"]), "people.yml")
        content = new_city_people.to_yaml
      end

      FileUtils.mkdir_p(File.dirname(city_people_path))
      File.write(city_people_path, content)
    end

    def self.people_with_names(people)
      people.select { |person| person["name"].present? }
    end
  end
end
