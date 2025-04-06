# frozen_string_literal: true

# Helper methods for all scrapers
require_relative "../path_helper"

module Scrapers
  class Standard
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_people.yml"))

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    def self.normalize_source_person(person)
      {
        "name" => person["name"],
        "image" => person["image"],
        "positions" => person["positions"],
        "email" => person["email"],
        "phone_number" => person["phone_number"],
        "website" => person["website"],
        "sources" => person["sources"]
      }
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
          "value" => format_phone_number(person["phone_number"]),
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

      formatted_person["other_names"] = []
      start_term_date = person["start_term_date"].present? ? format_date(person["start_term_date"]) : nil
      end_term_date = person["end_term_date"].present? ? format_date(person["end_term_date"]) : nil

      if person["positions"].present? && person["positions"].is_a?(Array)
        formatted_person["other_names"] = person["positions"].map do |position|
          { "note" => nil,
            "name" => position,
            "start_date" => start_term_date,
            "end_date" => end_term_date }
        end
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

    def self.get_website(person)
      person["links"].find { |link| link["url"].present? && link["url"].include?("http") }&.dig("url")
    end

    def self.format_date(date)
      date = Date.parse(date)
      date.strftime("%Y-%m-%d")
    rescue StandardError
      nil
    end

    def self.format_phone_number(phone) # rubocop:disable Metrics/AbcSize,Metrics/CyclomaticComplexity,Metrics/MethodLength,Metrics/PerceivedComplexity
      return nil if phone.nil?

      # TODO: Only support one phone # for now
      phone = phone.first if phone.is_a?(Array)
      phone.strip.empty?

      # Extract digits and plus sign for international numbers
      digits = phone.gsub(/[^\d+]/, "")

      # Handle extensions (e.g., "123-456-7890 ext. 123")
      base_number, extension = digits.split(/ext|x/i, 2).map(&:strip)

      # Reject numbers that are too short (e.g., 7-digit numbers)
      return nil if base_number.length < 10

      # U.S. Number Formatting
      formatted = case base_number.length
                  when 10
                    "(#{base_number[0..2]}) #{base_number[3..5]}-#{base_number[6..9]}"
                  when 11
                    if base_number.start_with?("1") # U.S. country code
                      "(#{base_number[1..3]}) #{base_number[4..6]}-#{base_number[7..10]}"
                    else
                      "+#{base_number}" # Assume international
                    end
                  else
                    "+#{base_number}" # Default to international
                  end

      # Append extension if present
      extension ? "#{formatted} ext. #{extension}" : formatted
    end
  end
end
