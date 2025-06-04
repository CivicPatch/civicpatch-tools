# frozen_string_literal: true

module Core
  module PersonManager
    class Utils
      SORT_KEYS = %w[name roles divisions image cdn_image email phone_number website start_date end_date sources].freeze

      def self.normalize_role(government_type, role)
        government_roles = Core::CityManager.roles(government_type)
        normalized_role = ""
        # First normalize the role to a standard format
        role_to_find = role&.downcase&.strip

        # First, check if the role is valid as-is
        found_role = government_roles.find { |r| r["role"]&.downcase == role_to_find }

        if found_role.present?
          normalized_role = found_role["role"]
        else # If not, check if it is an alias of another role
          aliased_role = government_roles.find { |r| r["aliases"]&.include?(role_to_find) }
          normalized_role = (aliased_role["role"] if aliased_role.present?)
        end

        # return the normalized role
        normalized_role.split(" ").map(&:capitalize)&.join(" ") if normalized_role.present?
      end

      def self.normalize_division(division)
        division_types = Core::CityManager.divisions
        # First normalize the division to a standard format
        division_to_find = division&.downcase&.strip

        return nil if division_to_find.blank?

        # First, check if the division is valid as-is
        found_division = division_types.keys.find { |d| division_to_find.start_with?(d) }
        if found_division.blank? # If not, check if it is an alias of another division
          aliased_division_key, _value = division_types.find do |_key, value|
            value["aliases"]&.any? { |alias_name| division_to_find.start_with?(alias_name) }
          end

          # Replace with the aliased division key if found
          division_to_find = aliased_division_key if aliased_division_key.present?
        end

        division_key, division_rest = division_to_find.split(" ", 2)

        # If the division identifier is a single word, attempt to format it
        division_rest = format_division_identifier(division_rest)

        normalized_division = [division_key, division_rest].compact.join(" ").strip

        # return the normalized division
        normalized_division.split(" ").map(&:capitalize)&.join(" ")
      end

      # NOTE: Assume no one is going to use non-numeric characters
      # when numbers go higher than 10
      def self.format_division_identifier(division_rest_string)
        number_words_in_english = %w[one two three four five six seven eight nine ten]
        number_words_in_roman = %w[i ii iii iv v vi vii viii ix x]

        division_identifier_to_find = division_rest_string&.downcase&.strip

        if number_words_in_english.include?(division_identifier_to_find)
          return (number_words_in_english.index(division_rest_string) + 1).to_s
        end

        if number_words_in_roman.include?(division_identifier_to_find)
          return (number_words_in_roman.index(division_rest_string) + 1).to_s
        end

        division_rest_string
      end

      def self.sort_people(government_type, people)
        sort_map = {} # {"roles", "divisions", "names"}

        government_roles = Core::CityManager.roles(government_type)
        role_order = government_roles.map { |r| r["role"].downcase }

        people.each_with_index do |person, index|
          sort_map[index] = {
            person: person,
            roles: person["roles"],
            divisions: person["divisions"],
            name: person["name"]
          }
        end

        sorted_values = sort_map.values.sort_by do |data|
          role = data[:roles]&.first&.downcase || ""
          role_index = role_order.index(role) || 999
          division = data[:divisions]&.first || ""
          name = data[:name] || ""

          [role_index, division, name]
        end

        sorted_values.map { |data| data[:person] }
      end

      def self.sort_keys(person)
        sorted = {}
        SORT_KEYS.each do |key|
          sorted[key] = person[key]
        end
        sorted
      end
    end
  end
end
