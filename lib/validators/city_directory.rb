# frozen_string_literal: true

require_relative "wa/city_directory"

module Validators
  # List of elected officials for the city (municipality/place)
  class CityDirectory
    CONFIG_PATH = PathHelper.project_path(File.join("config", "city_directory.yml"))
    VALIDATORS = [SOURCE = "source", GEMINI = "gemini"].freeze

    def self.config
      @config ||= YAML.load_file(CONFIG_PATH)
    end

    def self.google_gemini
      @google_gemini ||= Services::GoogleGemini.new
    end

    def self.get_state_validator(state)
      case state
      when "wa"
        Validators::Wa::CityDirectory
      else
        raise "No validator found for state: #{state}"
      end
    end

    def self.validate_directory(state, gnis)
      city_entry = CityScrape::StateManager.get_city_entry_by_gnis(state, gnis)
      city = city_entry["name"]
      url = city_entry["website"]

      # Gather all sources

      # Source Validator, the most trusted source
      source_validator = get_state_validator(state)
      city_directory_source = source_validator.get_source_city_directory(gnis)

      # Gemini Validator, an LLM that searches a URL for a city directory
      # city_directory_gemini = google_gemini.get_city_directory(city, url)

      # Save the directories to a file
      city_path = CityScrape::CityManager.get_city_path(state, city_entry)
      directories_folder = PathHelper.project_path(File.join(city_path, "directories"))
      FileUtils.mkdir_p(directories_folder)
      File.write(File.join(directories_folder, "city_directory_source.yml"), city_directory_source)
      # File.write(File.join(directories_folder, "city_directory_gemini.yml"), city_directory_gemini)

      # Compare the two
      # Validators::Utils.compare_people_across_sources(
      #  [city_directory_source, city_directory_gemini],
      #  [1.0, 0.5]
      # )

      contested_people = {
        "Alice Smith" => {
          positions: {
            disagreement_score: 0.0,
            values: [["Mayor"], ["Mayor"]]
          },
          email: {
            disagreement_score: 0.0,
            values: ["alice.smith@example.com", "alice.smith@example.com"]
          },
          phone: {
            disagreement_score: 0.2,
            values: %w[1234567890 123-456-7890]
          },
          website: {
            disagreement_score: 0.5,
            values: ["alice.com", "alice.org"]
          }
        },
        "Bob Jones" => {
          positions: {
            disagreement_score: 0.5,
            values: [["Council Member"], ["Councilman"]]
          },
          email: {
            disagreement_score: 0.0,
            values: ["bob.jones@example.com", "bob.jones@example.com"]
          },
          phone: {
            disagreement_score: 0.0,
            values: %w[555-123-4567 555-123-4567]
          },
          website: {
            disagreement_score: 0.4,
            values: ["bob.com", "bob-jones.com"]
          }
        }
      }

      {
        contested_people: contested_people,
        agreement_score: 0.75
      }
    end

    def self.to_markdown_table(contested_people)
      # Initialize the header for the table
      headers = ["Name", "Field", "Disagreement Score", "Values"]
      table = []

      # Loop through each person in the contested_people data
      contested_people.each do |name, fields|
        # For each contested field, add a row to the table
        fields.each do |field, field_data|
          row = [
            name,
            field.to_s.capitalize, # Capitalize the field name for readability
            field_data[:disagreement_score].round(2), # Round the disagreement score for cleaner output
            field_data[:values].map(&:to_s).join(", ") # Convert the values array to a string
          ]
          table << row
        end
      end

      # Now build the markdown table string
      markdown = "| #{headers.join(" | ")} |" # Add the headers
      markdown += "\n| #{"-" * (headers.join(" | ").length - 2)} |" # Add a separator line
      table.each do |row|
        markdown += "\n| #{row.join(" | ")} |" # Add the data rows
      end

      markdown
    end

    def self.approve_reasons_to_markdown(approve, approve_reasons)
      approve_text = approve ? "✅ Looks good to me!" : "❌ Found some differences in actual vs expected"
      markdown = []
      markdown << "**#{approve_text}:**"
      markdown << "## Reasons"
      approve_reasons.each do |reason|
        markdown << "- #{reason}"
      end
      markdown.join("\n")
    end

    def self.diff_to_markdown(comparison_results) # rubocop:disable Metrics/AbcSize,Metrics/MethodLength
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
