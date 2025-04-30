module Core
  class PersonResolver
    def self.same_last_name?(person_name1, person_name2)
      name1 = person_name1.split(" ").last.downcase
      name2 = person_name2.split(" ").last.downcase
      name1 == name2
    end

    def self.same_email?(person_email1, person_email2)
      return false if person_email1.nil? || person_email2.nil?

      person_email1.downcase == person_email2.downcase
    end

    def self.same_website?(person_website1, person_website2)
      return false if person_website1.nil? || person_website2.nil?

      person_website1.downcase == person_website2.downcase
    end

    def self.similar_name?(person_name1, person_name2)
      (person_name1.include?(person_name2) ||
        person_name2.include?(person_name1)) && same_last_name?(person_name1, person_name2)
    end

    def self.match_by_name(people_config, haystack_people, needle_person)
      haystack_people.each do |haystack_person|
        return haystack_person if similar_name?(haystack_person["name"], needle_person["name"])

        next if people_config.nil?

        canonical_name = haystack_person["name"]
        person_config = people_config[canonical_name]

        return haystack_person if name_in_config?({ canonical_name => person_config }, needle_person["name"])
      end

      nil
    end

    def self.name_in_config?(people_config, needle_person_name)
      return false if people_config.nil?

      return true if people_config.keys.any? { |key| similar_name?(key, needle_person_name) } ||
                     people_config.values.any? do |person_config|
                       people_config["other_names"]&.include?(needle_person_name)
                     end

      false
    end

    def self.match_by_weak_ties(haystack_people, needle_person)
      haystack_people.each do |haystack_person|
        return haystack_person if same_last_name?(haystack_person["name"], needle_person["name"]) &&
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
      found_person = match_by_name(people_config, people, maybe_new_person) ||
                     match_by_weak_ties(people, maybe_new_person)

      name = get_canonical_name(people_config, maybe_new_person)
      if people_config[name].present? && maybe_new_person["name"] != name
        maybe_add_other_name(people_config, name, maybe_new_person)
      else
        people_config[name] = { "other_names" => [] }
      end

      [found_person, people_config]
    end

    def self.maybe_add_other_name(people_config, person_key, maybe_new_person)
      other_names = people_config[person_key]["other_names"] ||= []
      return if other_names.include?(maybe_new_person["name"])

      other_names << maybe_new_person["name"]
      people_config[person_key]["other_names"] = other_names
    end
  end
end
