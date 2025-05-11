# frozen_string_literal: true

require "namae"

module Resolvers
  class PersonResolver
    def self.same_email?(person1, person2)
      emails1 = person1["email"].present? ? [person1["email"]] : person1["emails"]&.map { |email| email["data"] } || []
      emails2 = person2["email"].present? ? [person2["email"]] : person2["emails"]&.map { |email| email["data"] } || []

      emails1.compact.any? { |email| emails2.compact.any? { |e| e.downcase == email.downcase } }
    end

    def self.same_website?(person1, person2)
      websites1 = if person1["website"].present?
                    [person1["website"]]
                  else
                    person1["websites"]&.map do |website|
                      website["data"]
                    end || []
                  end
      websites2 = if person2["website"].present?
                    [person2["website"]]
                  else
                    person2["websites"]&.map do |website|
                      website["data"]
                    end || []
                  end

      websites1.compact.any? { |website| websites2.compact.any? { |w| w.downcase == website.downcase } }
    end

    def self.parse_name(person_name)
      # TODO: there can be bugs with this
      # Example: "David (Narh) Amanor" => []
      # Example: "Abigail Elder => []"
      name = Namae.parse(person_name).first

      given_name = name&.given
      last_name = name&.family

      [given_name, last_name]
    end

    def self.similar_name?(person_name1, person_name2)
      return true if person_name1 == person_name2

      # Ignore initials
      given_name1, last_name1 = parse_name(person_name1)
      given_name2, last_name2 = parse_name(person_name2)

      return false if given_name1.blank? || last_name1.blank? || given_name2.blank? || last_name2.blank?

      # Ignore Prefixed names
      ((person_name1&.downcase&.include?(person_name2&.downcase) ||
        person_name2&.downcase&.include?(person_name1&.downcase)) && last_name1&.downcase == last_name2&.downcase) ||
        # Ignore initials
        ((given_name1.downcase&.include?(given_name2&.downcase) ||
          given_name2.downcase&.include?(given_name1.downcase)) && last_name1&.downcase == last_name2&.downcase) ||
        (given_name1&.downcase == given_name2&.downcase && last_name1&.downcase == last_name2&.downcase)
    end

    def self.find_by_name(people_config, haystack_people, needle_person_name)
      haystack_people.each do |haystack_person|
        return haystack_person if similar_name?(haystack_person["name"], needle_person_name)

        next if people_config.nil?

        canonical_name = get_canonical_name(people_config, haystack_person)
        person_config = people_config[canonical_name]

        return haystack_person if name_in_config?({ canonical_name => person_config },
                                                  needle_person_name)
      end

      nil
    end

    def self.name_in_config?(people_config, needle_person_name)
      return false if people_config.nil?

      return true if people_config.keys.any? { |key| similar_name?(key, needle_person_name) } ||
                     people_config.values.any? do |person_config|
                       next if person_config.nil?

                       person_config["other_names"]&.include?(needle_person_name)
                     end

      false
    end

    def self.match_by_weak_ties(haystack_people, needle_person)
      _, needle_last_name = parse_name(needle_person["name"])
      haystack_people.each do |haystack_person|
        _, haystack_last_name = parse_name(haystack_person["name"])
        next if haystack_last_name.blank? # TODO: namae sometimes can't handle different formats of names
        next if needle_last_name.blank?

        return haystack_person if haystack_last_name.downcase == needle_last_name.downcase &&
                                  (same_email?(haystack_person, needle_person) ||
                                  same_website?(haystack_person, needle_person))
      end

      nil
    end

    def self.get_canonical_name(people_config, person)
      return person["name"] if people_config.nil?

      people_config.keys.find do |key|
        return key if name_in_config?({ key => people_config[key] }, person["name"])
      end

      person["name"]
    end

    def self.find_existing_person(people_config, people, maybe_new_person)
      updated_people_config = people_config.dup
      found_person = find_by_name(updated_people_config, people, maybe_new_person["name"]) ||
                     match_by_weak_ties(people, maybe_new_person)

      canonical_name = get_canonical_name(people_config, maybe_new_person)

      updated_people_config = maybe_add_other_name(people_config, canonical_name, maybe_new_person)

      [found_person, updated_people_config]
    end

    def self.maybe_add_other_name(people_config, canonical_name, maybe_new_person)
      person_config = people_config[canonical_name]

      if !person_config.present?
        people_config[canonical_name] = { "other_names" => [] }
      elsif !name_in_config?({ canonical_name => person_config }, maybe_new_person["name"])
        other_names = person_config["other_names"] ||= []
        other_names << maybe_new_person["name"]
        people_config[canonical_name]["other_names"] = other_names
      end

      people_config
    end
  end
end
