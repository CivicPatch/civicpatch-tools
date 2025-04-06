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

      def self.normalize_positions(positions, positions_config)
        alias_map = generate_alias_map(positions_config)
        divisions_map = generate_divisions_map(positions_config)

        positions.flat_map do |position|
          normalized_position = position.downcase.strip

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
            normalized_position.include?(role_config["role"].downcase)
          end

          next [matching_position["role"]] if matching_position.present?

          ## Try to find aliases
          puts "alias is #{alias_map}"
          matching_alias = alias_map.keys.find do |k|
            normalized_position.include?(k)
          end

          next [alias_map[matching_alias]] if matching_alias.present?

          [normalized_position]
        end
      end

      def self.normalize_division_string(position_string)
        unwanted_prefixes = ["no", "no.", "#"]

        division, rest = position_string.split(" ", 2)
        return position_string unless rest

        unwanted_prefixes.each do |prefix|
          rest = rest.delete_prefix(prefix)
        end

        [division, rest].join(" ").strip
      end

      # This method sorts positions by role, division, and then alphabetically
      def self.sort_positions(positions, positions_config)
        role_order = positions_config["roles"].each_with_index.to_h do |role_config, index|
          [role_config["role"].downcase, index]
        end

        positions.sort_by do |position|
          role = positions_config["roles"].find do |role_config|
            position.downcase.include?(role_config["role"].downcase)
          end
          division = nil

          role&.dig("divisions")&.each do |division_name|
            if position.downcase.include?(division_name.downcase)
              division = division_name
              break
            end
          end

          [role_order[role["role"].downcase] || Float::INFINITY, role["divisions"]&.index(division) || Float::INFINITY,
           position.downcase]
        end
      end
    end
  end
end
