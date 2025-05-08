# frozen_string_literal: true

module Utils
  class PhoneHelper
    def self.format_phone_number(phone) # rubocop:disable Metrics/AbcSize,Metrics/CyclomaticComplexity,Metrics/MethodLength,Metrics/PerceivedComplexity
      return nil if phone.nil?

      # TODO: Only support one phone # for now
      phone = phone.first if phone.is_a?(Array)
      return nil if phone.strip.empty?

      # Check for extension before removing non-digits
      has_ext = phone.match(/ext(?:ension)?|x/i)

      # Split by extension separator
      base_phone, extension = if has_ext
                                phone.split(/ext(?:ension)?|x/i, 2).map(&:strip)
                              else
                                [phone, nil]
                              end

      # Now extract digits from base phone, preserving the + sign if it exists
      has_plus = base_phone.start_with?("+")
      base_digits = base_phone.gsub(/[^\d]/, "")

      # Reject numbers that are too short (e.g., 7-digit numbers)
      return nil if base_digits.nil? || base_digits.empty?
      return nil if base_digits.length < 10

      # Extract digits from extension if present
      ext_digits = extension&.gsub(/[^\d]/, "")

      # U.S. Number Formatting
      formatted = case base_digits.length
                  when 10
                    "(#{base_digits[0..2]}) #{base_digits[3..5]}-#{base_digits[6..9]}"
                  when 11
                    if base_digits.start_with?("1") # U.S. country code
                      "(#{base_digits[1..3]}) #{base_digits[4..6]}-#{base_digits[7..10]}"
                    else
                      # International with 11 digits
                      has_plus ? "+#{base_digits}" : base_digits
                    end
                  else
                    # International or other format
                    has_plus ? "+#{base_digits}" : base_digits
                  end

      # Append extension if present
      ext_digits ? "#{formatted} ext. #{ext_digits}" : formatted
    end
  end
end
