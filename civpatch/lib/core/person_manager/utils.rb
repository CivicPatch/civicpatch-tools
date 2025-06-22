# frozen_string_literal: true

require "core/city_manager"

module Core
  module PersonManager
    class Utils
      SORT_KEYS = %w[name roles divisions image cdn_image email phone_number website start_date end_date sources].freeze

      def self.normalize_role(government_type, role)
        government_roles = Core::CityManager.roles(government_type)
        normalized_roles = []
        # First normalize the role to a standard format
        roles_to_find = role&.downcase&.strip&.split(",")&.map(&:strip)

        # First, check if the role is valid as-is
        roles_to_find.each do |role_to_find|
          found_role = government_roles.find { |r| r["role"]&.downcase == role_to_find }

          if found_role.present?
            normalized_role = found_role["role"]
          else # If not, check if it is an alias of another role
            aliased_role = government_roles.find { |r| r["aliases"]&.include?(role_to_find) }
            normalized_role = (aliased_role["role"] if aliased_role.present?)
          end

          # return the normalized role
          if normalized_role.present?
            normalized_role = normalized_role.split(" ").map(&:capitalize)&.join(" ")
            normalized_roles << normalized_role
          end
        end

        normalized_roles
      end

      def self.normalize_division(division)
        division_types = Core::CityManager.divisions
        division_to_find = division&.downcase&.strip

        return nil if division_to_find.blank?

        # Dynamically handle division types based on `division_types`
        division_keys = division_types.keys.map(&:downcase)
        matched_key = division_keys.find { |key| division_to_find.match(/\b#{key}\b/) }

        if matched_key
          # Extract the division key (e.g., "Ward" or "District")
          division_key = matched_key.capitalize

          # Extract the numeric or ordinal identifier (e.g., "1st", "3rd")
          division_rest = division_to_find.gsub(/\b#{matched_key}\b/i, "").strip
          division_rest = format_division_identifier(division_rest)

          return [division_key, division_rest].compact.map(&:capitalize).join(" ").strip
        end

        # Check if the division is valid as-is
        found_division = division_types.keys.find { |d| division_to_find.include?(d) }
        if found_division.blank? # Check for aliases
          aliased_division_key, _value = division_types.find do |_key, value|
            value["aliases"]&.any? { |alias_name| division_to_find.include?(alias_name) }
          end

          division_to_find = aliased_division_key if aliased_division_key.present?
        end

        division_key, division_rest = division_to_find.split(" ", 2)
        division_rest = format_division_identifier(division_rest)

        normalized_division = [division_key, division_rest].compact.join(" ").strip
        normalized_division.split(" ").map(&:capitalize).join(" ")
      end

      # NOTE: Assume no one is going to use non-numeric characters
      # when numbers go higher than 10
      def self.format_division_identifier(division_rest_string)
        number_words_in_english = %w[one two three four five six seven eight nine ten]
        number_words_in_roman = %w[i ii iii iv v vi vii viii ix x]

        division_identifier_to_find = division_rest_string&.downcase&.strip

        return "" if division_identifier_to_find.blank?

        # Remove quotation marks (curly and normal) and parentheses
        division_identifier_to_find = division_identifier_to_find.gsub(/["“”‘’()]/, "").strip
        # Remove prefixes like "no1", "no 1", "no.1", "no. 1", "#1", "# 1", "number 1"
        division_identifier_to_find = division_identifier_to_find.sub(/^(no\.?\s*|#\.?\s*|number\s*)/, "").strip
        # Remove ordinal suffixes like "rd", "st", "nd", "th" ONLY if preceded by a number
        division_identifier_to_find = division_identifier_to_find.gsub(/(\d+)(rd|st|nd|th)$/i, '\1').strip

        # Convert English or Roman numerals to numbers
        if number_words_in_english.include?(division_identifier_to_find)
          return (number_words_in_english.index(division_identifier_to_find) + 1).to_s
        end

        if number_words_in_roman.include?(division_identifier_to_find)
          return (number_words_in_roman.index(division_identifier_to_find) + 1).to_s
        end

        division_identifier_to_find
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

      def self.sort_keys(government_type, person)
        government_roles = Core::CityManager.roles(government_type)
        sorted = {}
        SORT_KEYS.each do |key|
          if key == "roles"
            # Sort roles by their role index
            sorted_roles = person[key].sort_by do |role|
              role_index = government_roles.find_index { |r| r["role"].casecmp(role).zero? }
              role_index.nil? ? 999 : role_index
            end
            sorted[key] = sorted_roles
          else
            sorted[key] = person[key]
          end
        end
        sorted
      end
    end
  end
end
