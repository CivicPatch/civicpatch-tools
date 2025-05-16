# frozen_string_literal: true

module Utils
  class NameHelper
    def self.valid_name?(name)
      name.present? && name.strip.length.positive? && name.split(" ").length > 1
    end

    def self.format_name(name)
      name.squeeze(" ").strip
    end
  end
end
