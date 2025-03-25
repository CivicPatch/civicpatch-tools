# frozen_string_literal: true

# Helper methods for all scrapers

module Scrapers
  class Standard
    def self.format_phone_number(phone_number)
      # Remove all non-digit characters
      phone_number = phone_number.gsub(/\D/, '')

      # Format the phone number
      phone_number.gsub(/(\d{3})(\d{3})(\d{4})/, '(\1) \2-\3')
    end
  end
end
