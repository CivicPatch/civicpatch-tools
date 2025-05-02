module Core
  class PersonResolver
    def self.same_email?(person_email1, person_email2)
      return false if person_email1.nil? || person_email2.nil?

      person_email1.downcase == person_email2.downcase
    end

    def self.same_website?(person_website1, person_website2)
      return false if person_website1.nil? || person_website2.nil?

      person_website1.downcase == person_website2.downcase
    end

    def self.parse_name(person_name)
      parts = person_name.split(" ")
      first_name = parts.first
      last_name = parts.last

      [first_name, last_name]
    end

    def self.similar_name?(person_name1, person_name2)
      # Ignore initials
      first_name1, last_name1 = parse_name(person_name1)
      first_name2, last_name2 = parse_name(person_name2)

      # Ignore Prefixed names
      ((person_name1.include?(person_name2) ||
        person_name2.include?(person_name1)) && last_name1 == last_name2) ||
        # Ignore initials
        (first_name1 == first_name2 && last_name1 == last_name2)
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
        return haystack_person if haystack_last_name.downcase == needle_last_name.downcase &&
                                  (same_email?(haystack_person["email"], needle_person["email"]) ||
                                  same_website?(haystack_person["website"], needle_person["website"]))
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
      found_person = find_by_name(people_config, people, maybe_new_person["name"]) ||
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
