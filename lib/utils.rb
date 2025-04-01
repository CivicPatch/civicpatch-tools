# frozen_string_literal: true

# Utils module provides helper methods for formatting data, such as phone numbers.
# These methods ensure consistency across the application and handle various edge cases.
module Utils
  def self.format_position(position)
    position_title = position.downcase
    case position_title
    when "councilmember", "council_member"
      "Council Member"
    else
      position_title.split(" ").map(&:capitalize).join(" ")
    end
  end

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

  def self.format_phone_number(phone) # rubocop:disable Metrics/AbcSize,Metrics/CyclomaticComplexity,Metrics/MethodLength,Metrics/PerceivedComplexity
    return nil if phone.nil? || phone.strip.empty?

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

  # TODO: needs better logic
  def self.same_person?(person_a, person_b)
    person_a_names = person_a["name"].downcase.split(" ")
    person_b_names = person_b["name"].downcase.split(" ")

    person_a_names.first == person_b_names.first &&
      person_a_names.last == person_b_names.last
  end
end
