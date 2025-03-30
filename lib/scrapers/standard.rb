# frozen_string_literal: true

# Helper methods for all scrapers

module Scrapers
  class Standard
    def self.valid_name?(name)
      name.present? && name.split.length > 1
    end

    # See: https://open-civic-data.readthedocs.io/en/latest/data/person.html#basics
    def self.format_person(person, source_url)
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
          "value" => person["email"],
          "label" => "Email"
        }
      end
      # NOT IMPLEMENTING - standard says these are required
      # but can be null. But is that useful for anyone?
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

      formatted_person["identifiers"] = []
      formatted_person["other_names"] = []

      if person["position"].present?
        formatted_person["other_names"] << {
          "note" => nil,
          "name" => format_position(person["position"]),
          "start_date" => person["start_term_date"].present? ? person["start_term_date"] : nil,
          "end_date" => person["end_term_date"].present? ? person["end_term_date"] : nil
        }
      end

      if person["position_misc"].present?
        person["position_misc"].each do |misc|
          formatted_person["identifiers"] << {
            "note" => nil,
            "name" => "#{format_position(misc["type"])} #{misc["value"]}",
            "start_date" => nil,
            "end_date" => nil
          }
        end
      end

      formatted_person["updated_at"] = Time.now.strftime("%Y-%m-%d")
      formatted_person["created_at"] = Time.now.strftime("%Y-%m-%d")
      formatted_person["sources"] = [{ url: source_url, note: nil }]

      formatted_person
    end

    def self.format_phone_number(phone_number)
      # Remove all non-digit characters
      phone_number = phone_number.gsub(/\D/, '')

      # Format the phone number
      phone_number.gsub(/(\d{3})(\d{3})(\d{4})/, '(\1) \2-\3')
    end

    def self.format_position_misc(position_misc)
      position_misc.map do |misc|
        misc["type"] = "role" if misc["type"].blank?
        misc["value"] = misc["value"]
                        .split(" ")
                        .map(&:downcase)
                        .map { |word| word.gsub(".", "") }
                        .join("_")
        misc
      end
    end

    def self.format_position(position_name)
      position_name.split("_").map(&:capitalize).join(" ")
    end
  end
end
