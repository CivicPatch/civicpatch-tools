# frozen_string_literal: true

module Core
  module PersonManager
    class Utils
      def self.generate_alias_map(positions_configs)
        alias_map = {}
        positions_configs.each do |role_config|
          role = role_config["role"].downcase
          role_config["aliases"]&.each do |alias_name|
            alias_map[alias_name.downcase] = role
          end
        end
        alias_map
      end

      def self.generate_divisions_map(positions_configs)
        divisions_map = {}
        positions_configs.each do |role_config|
          role = role_config["role"].downcase
          role_config["divisions"]&.each do |division_name|
            divisions_map[division_name.downcase] = role
          end
        end
        divisions_map
      end

      def self.normalize_positions(positions, government_types_config)
        positions_config = government_types_config["positions"]
        alias_map = generate_alias_map(positions_config)
        divisions_map = generate_divisions_map(positions_config)
        excluded_positions = government_types_config["exclude_positions"] || []

        positions.flat_map do |position|
          normalized_position = position.downcase.strip

          # Check if the normalized position EXACTLY matches any excluded position
          next [] if excluded_positions.include?(normalized_position)

          ## Try to find divisions
          matching_division = divisions_map.keys.find { |k, _v| normalized_position.include?(k) }

          if matching_division.present?
            division_string = normalize_division_string(
              normalized_position.slice(
                normalized_position.index(matching_division)..
              )
            )
            next [divisions_map[matching_division], division_string]
          end

          ## Try to find a matching role
          matching_position = positions_config.find do |role_config|
            normalized_position == role_config["role"].downcase
          end

          next [matching_position["role"]] if matching_position.present?

          ## Try to find aliases
          matching_alias = alias_map.keys.find do |k|
            normalized_position.include?(k)
          end

          next [alias_map[matching_alias]] if matching_alias.present?

          # TODO: let's toss anything we don't recognize
          # [normalized_position]
          []
        end.uniq
      end

      def self.format_position(position)
        position.split(" ").map(&:capitalize).join(" ")
      end

      def self.normalize_division_string(position_string)
        unwanted_prefixes = ["no.", "no", "#"]

        division, rest = position_string.split(" ", 2)
        return position_string unless rest

        unwanted_prefixes.each do |prefix|
          rest = rest.delete_prefix(prefix)
        end

        [division, rest].join(" ").split.join(" ")
      end

      def self.sort_positions(positions, positions_config)
        normalized = normalize_positions(positions, positions_config)
        apply_sort_order(normalized, positions_config["positions"])
      end

      def self.find_divisions(positions, positions_config)
        division_matches = {}

        positions.each do |position|
          normalized_position = position.downcase.strip
          positions_config.each do |role_config|
            division_match = role_config["divisions"]&.find do |division|
              normalized_position.include?(division.downcase)
            end
            division_matches[division_match] = normalized_position if division_match.present?
          end
        end

        division_matches
      end

      def self.find_roles(positions, positions_config)
        role_matches = []
        positions.each do |position|
          normalized_position = position.downcase.strip
          role_match = positions_config.find do |role_config|
            normalized_position == role_config["role"].downcase
          end
          role_matches << role_match["role"] if role_match.present?
        end

        role_matches
      end

      def self.sort_people(people, government_types_config)
        positions_config = government_types_config["positions"]
        # Map role names to their order based on the provided config
        role_order = positions_config.each_with_index.to_h do |role_config, index|
          [role_config["role"].downcase, index]
        end

        # Get the list of all divisions (assuming it's a flat list of strings)

        sort_map = {} # {"roles", "divisions", "names"}
        people.each_with_index do |person, index|
          roles = find_roles(person["positions"], positions_config)
          divisions = find_divisions(person["positions"], positions_config)

          sort_map[index] = {
            person: person,
            roles: roles,
            divisions: divisions,
            names: person["name"],
            name: person["name"]
          }
        end

        sort_map.values.sort_by do |data|
          primary_role = data[:roles].find { |r| role_order.key?(r.downcase) } || "zzz"
          role_index = role_order[primary_role.downcase] || Float::INFINITY

          division_key = data[:divisions].keys.first || ""
          division_val = data[:divisions].values.first || ""
          division_combo = "#{division_key} #{division_val}".downcase

          name = data[:name] || ""

          [role_index, division_combo, name]
        end.map { |data| data[:person] }
      end

      private_class_method def self.apply_sort_order(normalized_positions, positions_config)
        # Create role_order hash
        role_order = positions_config.each_with_index.to_h do |role_config, index|
          [role_config["role"].downcase, index]
        end
        # Get divisions_list
        divisions_list = positions_config.flat_map { |role_config| role_config["divisions"] }.compact

        # Apply the sort_by logic
        normalized_positions.sort_by do |position|
          division_match = divisions_list.find { |division| position.include?(division) }
          [
            role_order[position] || Float::INFINITY,
            division_match ? 0 : 1,
            position
          ]
        end
      end
    end
  end
end
