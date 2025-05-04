# frozen_string_literal: true

module Utils
  class PhoneHelper
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
      return nil if base_number.nil?
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
