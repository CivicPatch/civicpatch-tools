# frozen_string_literal: true

# Helper methods for all scrapers
require_relative "../utils"
require_relative "../path_helper"

module Scrapers
  class Standard
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_directory.yml"))

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    # See: https://open-civic-data.readthedocs.io/en/latest/data/person.html#basics
    def self.format_person(person, source_url, website_url = nil)
      formatted_person = {}

      formatted_person["name"] = person["name"]
      formatted_person["image"] = person["image"]
      formatted_person["contact_details"] = []
      if person["phone_number"].present?
        formatted_person["contact_details"] << {
          "note" => nil,
          "type" => "phone",
          "value" => Utils.format_phone_number(person["phone_number"]),
          "label" => "Phone"
        }
      end
      if person["email"].present?
        formatted_person["contact_details"] << {
          "note" => nil,
          "type" => "email",
          "value" => person["email"].downcase,
          "label" => "Email"
        }
      end

      formatted_person["links"] = []
      # Don't re-add if the source url is the same as the website url
      if website_url.present? && (source_url != website_url)
        formatted_person["links"] << { "note" => nil, "url" => website_url }
      end

      # NOT IMPLEMENTING - standard says these are required
      # but can be null.
      # formatted_person["links"] = []
      # formatted_person["sort_name"] = nil
      # formatted_person["family_name"] = nil
      # formatted_person["given_name"] = nil
      # formatted_person["gender"] = nil
      # formatted_person["summary"] = nil
      # formatted_person["national_identity"] = nil
      # formatted_person["biography"] = nil
      # formatted_person["birth_date"] = nil
      # formatted_person["death_date"] = nil
      # formatted_person["identifiers"] = []
      formatted_person["other_names"] = []
      start_term_date = person["start_term_date"].present? ? format_date(person["start_term_date"]) : nil
      end_term_date = person["end_term_date"].present? ? format_date(person["end_term_date"]) : nil

      if person["positions"].present? && person["positions"].is_a?(Array)
        formatted_person["other_names"] = determine_positions(person["positions"], start_term_date, end_term_date)
      end

      formatted_person["updated_at"] = Time.now.strftime("%Y-%m-%d")
      formatted_person["created_at"] = Time.now.strftime("%Y-%m-%d")
      formatted_person["sources"] = [{ "url" => source_url, "note" => nil }]

      formatted_person
    end

    def self.valid_name?(name)
      name.present? && name.strip.length.positive? && name.split(" ").length > 1
    end

    # Determine positions via config.yml
    def self.key_positions
      config.dig("government_types", "mayor_council", "key_positions") || []
    end

    def self.alias_map
      key_positions.each_with_object({}) do |position, map|
        next unless position.is_a?(Hash)

        position_name = position["role"]
        aliases = position["aliases"]
        aliases.each { |alias_name| map[alias_name.downcase] = position_name } if aliases.present?
      end
    end

    def self.implied_by_map
      key_positions.each_with_object({}) do |position, map|
        next unless position.is_a?(Hash)

        position_name = position["role"]
        implied_by = position["implied_by"] || []

        implied_by.each { |implied_term| map[implied_term] = position_name }
      end
    end

    def self.format_position(position)
      formatted = position.split(" ").map(&:capitalize).join(" ")
      formatted.gsub(/[^a-zA-Z0-9 ]/, "").squeeze(" ").strip
    end

    def self.determine_positions(positions, start_term_date, end_term_date)
      alias_map = self.alias_map
      implied_by_map = self.implied_by_map

      # Normalize positions by replacing aliases with standard names
      normalized_positions = positions.map { |pos| alias_map[pos.downcase] || pos }.uniq

      # Expand implied positions **only when relevant**
      expanded_positions = normalized_positions.dup

      # If any implied keyword (ward, district, seat, position) exists, add "council member"
      positions.each do |p|
        match = implied_by_map.keys.find do |implied_key|
          p.downcase.include?(implied_key.downcase)
        end

        expanded_positions << implied_by_map[match] if match
      end

      expanded_positions.uniq.map do |position|
        { "note" => nil,
          "name" => format_position(position),
          "start_date" => start_term_date,
          "end_date" => end_term_date }
      end
    end

    def self.get_website(person)
      person["links"].find { |link| link["url"].present? && link["url"].include?("http") }&.dig("url")
    end

    def self.format_date(date)
      date = Date.parse(date)
      date.strftime("%Y-%m-%d")
    rescue StandardError
      nil
    end
  end
end
