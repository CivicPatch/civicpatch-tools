# frozen_string_literal: true

# Utils module provides helper methods for formatting data, such as phone numbers.
# These methods ensure consistency across the application and handle various edge cases.
module Utils
  class DirectoryHelper
    # Convert city directory person object into a simpler person object
    # for simpler comparisons
    def self.format_simple(person_object)
      formatted = {
        "name" => person_object["name"]
      }

      image = person_object["image"]
      formatted["image"] = image if image.present?

      phone_number = person_object["contact_details"]&.find { |contact| contact["type"] == "phone" }&.dig("value")
      formatted["phone_number"] = phone_number if phone_number.present?

      email = person_object["contact_details"]&.find { |contact| contact["type"] == "email" }&.dig("value")
      formatted["email"] = email if email.present?

      website = person_object["links"]&.find { |link| link["url"].present? && link["url"].include?("http") }&.dig("url")
      formatted["website"] = website if website.present?

      positions = person_object["other_names"]&.map { |position| position["name"] } || []
      formatted["positions"] = positions.join(", ")

      formatted
    end
  end
end
