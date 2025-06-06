# frozen_string_literal: true

require "utils/url_helper"
require "utils/phone_helper"
require "core/person_manager/utils"

module Core
  class PeopleManager
    def self.get_people(state, geoid, type = nil)
      if type.present?
        people_file_path = Core::PathHelper.get_people_candidates_file_path(state, geoid, type)
        content = JSON.parse(File.read(people_file_path))
      else
        people_file_path = File.join(Core::PathHelper.get_data_city_path(state, geoid), "people.yml")
        content = if File.exist?(people_file_path)
                    YAML.safe_load(File.read(people_file_path))
                  else
                    []
                  end
      end

      content
    end

    def self.format_people(government_type, people_config, people)
      people_config ||= {}

      people = people.map do |person|
        name = person["name"]&.squeeze(" ")
        canonical_name = Resolvers::PersonResolver.get_canonical_name(people_config, person)
        person["name"] = if canonical_name.present?
                           canonical_name
                         else
                           name
                         end

        person["roles"] = Array(person["roles"])
                          .flat_map { |role| Core::PersonManager::Utils.normalize_role(government_type, role) }
                          .compact
                          .sort_by(&:downcase)
        person["divisions"] = Array(person["divisions"])
                              .map { |division| Core::PersonManager::Utils.normalize_division(division) }
                              .compact
                              .sort_by(&:downcase)

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

      people.reject { |person| person["roles"].count.zero? }
    end

    def self.update_people(
      municipality_context,
      new_city_people,
      directory_type = nil
    )
      updated_at = Time.now.strftime("%Y-%m-%d")
      new_city_people = new_city_people.map { |person| add_updated_at(person, updated_at) }

      state = municipality_context[:state]
      city_entry = municipality_context[:municipality_entry]

      if directory_type.present?
        city_people_path = Core::PathHelper.get_people_candidates_file_path(state, city_entry["geoid"],
                                                                            directory_type)
        content = JSON.pretty_generate(new_city_people)
      else
        city_people_path = File.join(Core::PathHelper.get_data_city_path(state, city_entry["geoid"]), "people.yml")
        content = new_city_people.to_yaml
      end

      FileUtils.mkdir_p(File.dirname(city_people_path))
      File.write(city_people_path, content)
    end

    def self.people_with_names(people)
      people.select { |person| person["name"].present? }
    end

    def self.add_updated_at(person, updated_at)
      person["updated_at"] = updated_at
      person
    end
  end
end
