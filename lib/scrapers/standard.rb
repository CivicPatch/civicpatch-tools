# frozen_string_literal: true

# Helper methods for all scrapers

module Scrapers
  class Standard
    def self.format_person(person)
      person["phone_number"] = format_phone_number(person["phone_number"]) if person["phone_number"].present?
      person["position_misc"] = format_position_misc(person["position_misc"]) if person["position_misc"].present?

      person
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
  end
end
