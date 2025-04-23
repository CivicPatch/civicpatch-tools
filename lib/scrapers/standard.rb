# frozen_string_literal: true

# Helper methods for all scrapers
require_relative "../path_helper"

module Scrapers
  class Standard
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_people.yml"))

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    def self.valid_name?(name)
      name.present? && name.strip.length.positive? && name.split(" ").length > 1
    end

    # Determine positions via config.yml
    def self.key_positions
      config.dig("government_types", "mayor_council", "key_positions") || []
    end

    def self.implied_by_map
      key_positions.each_with_object({}) do |position, map|
        next unless position.is_a?(Hash)

        position_name = position["role"]
        implied_by = position["implied_by"] || []

        implied_by.each { |implied_term| map[implied_term] = position_name }
      end
    end

    def self.format_position(position)
      formatted = position.split(" ").map(&:capitalize).join(" ")
      formatted.gsub(/[^a-zA-Z0-9 ]/, "").squeeze(" ").strip
    end

    def self.get_website(person)
      person["links"].find { |link| link["url"].present? && link["url"].include?("http") }&.dig("url")
    end

    def self.format_date(date)
      date = Date.parse(date)
      date.strftime("%Y-%m-%d")
    rescue StandardError
      nil
    end
  end
end
