# frozen_string_literal: true

require "text"

module Validators
  class Utils
    # Normalize text (downcase, strip whitespace)
    def self.normalize_text(text)
      text.to_s.strip.downcase
    end

    def self.normalize_phone_number(phone_number)
      phone_number.to_s.gsub(/\D/, "") # Keep only digits
    end

    # Normalize emails (ignore case)
    def self.normalize_email(email)
      return nil if email.nil?

      email = normalize_text(email)
      local, domain = email.split("@", 2)
      return email unless domain # If malformed, return as is

      normalized_local = local.gsub(".", "") # Remove all dots from the username
      "#{normalized_local}@#{domain}"
    end

    def self.normalize_url(url)
      return nil if url.nil?

      url = normalize_text(url)
      url.gsub("www.", "")
    end
  end
end
