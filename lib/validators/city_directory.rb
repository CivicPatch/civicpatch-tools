# frozen_string_literal: true

require_relative "wa/city_directory"

module Validators
  # List of elected officials for the city (municipality/place)
  class CityDirectory
    def self.get_state_validator(state)
      case state
      when "wa"
        Validators::Wa::CityDirectory
      else
        raise "No validator found for state: #{state}"
      end
    end

    def self.validate_directory(state, gnis, city_directory_to_validate)
      validator = get_state_validator(state)

      valid_simple_city_directory = validator.get_valid_city_directory(gnis)
      simple_city_directory_to_validate = city_directory_to_validate.map { |person| Utils.format_simple(person) }
      compare_key_positions(valid_simple_city_directory, simple_city_directory_to_validate)
    end

    def self.compare_key_positions(expected_partial, actual_partial)
      expected = expected_partial.select do |p|
        Scrapers::CityDirectory::KEY_POSITIONS.any? do |pos|
          p["positions"].include?(pos)
        end
      end

      actual = actual_partial.select do |p|
        Scrapers::CityDirectory::KEY_POSITIONS.any? do |pos|
          p["positions"].include?(pos)
        end
      end

      missing = expected.reject { |e| actual.any? { |a| Utils.same_person?(e, a) } }
      extra = actual.reject { |a| expected.any? { |e| Utils.same_person?(a, e) } }

      different = expected.map do |e|
        actual_match = actual.find { |a| Utils.same_person?(e, a) }
        next unless actual_match && !similar_positions(e["positions"], actual_match["positions"])

        { "name" => e["name"], "expected" => e["positions"], "actual" => actual_match["positions"] }
      end.compact

      { missing:, extra:, different: }
    end

    def self.approve_reasons_to_markdown(approve, approve_reasons)
      approve_text = approve ? "✅ Looks good to me!" : "❌ Found some differences in actual vs expected"
      markdown = []
      markdown << "## Reasons"
      markdown << "- **#{approve_text}:**"
      approve_reasons.each do |reason|
        markdown << "- #{reason}"
      end
      markdown.join("\n")
    end

    def self.diff_to_markdown(comparison_results)
      markdown = []

      unless comparison_results[:missing].empty?
        markdown << "## Missing People"
        comparison_results[:missing].each do |person|
          markdown << "- **#{person["name"]}** (#{person["positions"]})"
        end
        markdown << ""
      end

      unless comparison_results[:extra].empty?
        markdown << "## Extra People"
        comparison_results[:extra].each do |person|
          markdown << "- **#{person["name"]}** (#{person["positions"]})"
        end
        markdown << ""
      end

      unless comparison_results[:different].empty?
        markdown << "## Different Positions"
        comparison_results[:different].each do |person|
          markdown << "- **#{person["name"]}**"
          markdown << "  - Expected: #{person["expected"]}"
          markdown << "  - Actual: #{person["actual"]}"
        end
        markdown << ""
      end

      markdown.join("\n")
    end

    def self.similar_positions(positions_a, positions_b)
      positions_a.include?(positions_b) || positions_b.include?(positions_a)
    end
  end
end
