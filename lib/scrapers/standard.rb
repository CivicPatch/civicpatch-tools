# frozen_string_literal: true

# Helper methods for all scrapers

module Scrapers
  class Standard
    # See: https://open-civic-data.readthedocs.io/en/latest/data/person.html#basics
    def self.format_person(person, source_url, website_url)
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

      puts "Returning person: #{formatted_person.inspect}"

      formatted_person
    end

    def self.valid_name?(name)
      name.present? && name.strip.length.positive? && name.split(" ").length > 1
    end

    def self.format_phone_number(phone_number)
      # Remove all non-digit characters
      phone_number = phone_number.gsub(/\D/, "")

      # Format the phone number
      phone_number.gsub(/(\d{3})(\d{3})(\d{4})/, '(\1) \2-\3')
    end

    def self.format_position(position_type, position_value)
      type = position_type.downcase == "role" ? "" : position_type.capitalize
      value = position_value.split(" ").map(&:capitalize).join(" ")
      [type, value].join(" ").strip
    end

    def self.determine_positions(positions, start_term_date, end_term_date)
      position_types = positions.map { |position| position["type"] }.uniq
      position_values = positions.map { |position| position["value"] }.uniq

      valid_positions = ["council member", "council president", "council vice president", "mayor"]

      has_valid_positions = position_values.any? { |value| valid_positions.include?(value.downcase) }

      # If they have a district, ward, position, or seat, then they are a council member
      if !has_valid_positions && position_types.any? do |type|
        %w[district ward position seat].include?(type.downcase)
      end
        positions << { type: "role", value: "Council Member" }
      end

      positions.map do |position|
        { "note" => nil,
          "name" => format_position(position["type"], position["value"]),
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
    rescue Date::Error
      nil
    end
  end
end
