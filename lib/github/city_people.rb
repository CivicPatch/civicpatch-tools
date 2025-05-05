# frozen_string_literal: true

module GitHub
  class CityPeople
    def self.to_markdown_missing_people_table(all_sources, missing_people)
      return "" if missing_people.nil? || missing_people.empty?

      headers = ["Name", "Missing From"]
      table = []
      markdown = "### Missing People\n\n"

      missing_people.each do |name, sources|
        missing_from_sources = all_sources - sources
        table << [name, missing_from_sources.join(", ")]
      end

      markdown += "| #{headers.join(" | ")} |"
      separator_line = "| #{headers.map { |header| "-" * header.length }.join(" | ")} |"
      markdown += "\n#{separator_line}"
      table.each do |row|
        markdown += "\n| #{row.join(" | ")} |"
      end

      markdown
    end

    def self.to_markdown_disagreement_table(contested_fields, merged_person)
      # Prepare source headers
      source_names = contested_fields.map { |_, field_data| field_data[:values].keys }.flatten.uniq
      headers = ["Field", "Disagreement Score"] + source_names
      table = []

      contested_fields.each do |field, field_data|
        row = [
          field.to_s.split("_").map(&:capitalize).join(" "),
          field_data[:disagreement_score].round(2)
        ]

        merged_value = merged_person[field]

        source_names.each do |source_name|
          value = field_data[:values][source_name]
          display_value = format_display_value(value, merged_value)
          formatted_display_value = if values_match?(value, merged_value)
                                      display_value
                                    else
                                      "**#{display_value}** ❌"
                                    end

          row << formatted_display_value
        end

        table << row
      end

      # Build markdown string
      markdown = "| #{headers.join(" | ")} |"
      separator_line = "| #{headers.map { |header| "-" * header.length }.join(" | ")} |"
      markdown += "\n#{separator_line}"
      table.each do |row|
        markdown += "\n| #{row.join(" | ")} |"
      end

      markdown
    end

    def self.values_match?(source_value, merged_value)
      return true if source_value.nil? # Nil values don't contribute anything

      source_array = Array(source_value).compact
      merged_array = Array(merged_value).compact

      return false if source_array.empty?

      # Scalar comparison
      return source_array.first == merged_array.first if source_array.size == 1 && merged_array.size == 1

      # Check if any source values contributed
      (source_array & merged_array).any?
    end

    def self.format_display_value(source_value, merged_value)
      return "(missing)" if source_value.nil? || (source_value.is_a?(Array) && source_value.empty?)

      if source_value.is_a?(Array)
        source_value.map do |val|
          merged_array = Array(merged_value).compact
          merged_array.include?(val) ? val : "**#{val}**"
        end.join(", ")
      else
        source_value.to_s
      end
    end

    def self.generate_suggest_edit_markdown(
      merged_people, suggest_edit_details, missing_people, contested_people
    )
      action_item_summary = generate_readable_updates_needed_list(
        merged_people, missing_people, contested_people
      )
      return "" unless action_item_summary.present?

      case suggest_edit_details[:type]
      when "email"
        email = suggest_edit_details[:data]
        source_url = suggest_edit_details[:source_url]
        <<~MARKDOWN
          - [ ] (Optional) Notify the state source maintaners of any changes as needed
              - [ ] Verify the state source data at [#{source_url}](#{source_url})
              - [ ] Email the maintainer(s) at [#{email}](mailto:#{email})
          #{action_item_summary}
        MARKDOWN
      when "url"
        <<~MARKDOWN
          - [ ] (Optional) Update the state source directory: #{suggest_edit_details[:data]}
          #{action_item_summary}
        MARKDOWN
      end
    end

    def self.generate_readable_updates_needed_list(merged_people, missing_people, contested_people)
      source_to_update = "state_source"
      not_in_office_list = []
      updates_needed_markdown = ""

      missing_people.each_key do |name|
        not_in_office_list << name unless missing_people[name].include?(source_to_update)
      end
      not_in_office_markdown = not_in_office_list.map { |name| "- #{name}" }.join("\n")

      if not_in_office_markdown.present?
        not_in_office_markdown = "The following officials are no longer in office:\n#{not_in_office_markdown}"
      end

      contested_people.each do |contested_person_name, contested_fields|
        merged_person = merged_people.find { |person| person["name"] == contested_person_name }

        next if merged_person.nil?

        updates_needed = get_updates_needed(source_to_update, merged_person, contested_fields)

        next unless updates_needed.present? && updates_needed.count.positive?

        updates_needed_markdown += "**#{contested_person_name}**\n"
        updates_needed.each do |update_needed|
          updates_needed_markdown += "- #{update_needed}\n"
        end
      end

      if updates_needed_markdown.present?
        updates_needed_markdown = "The following officials may need updates to their records:\n#{
          updates_needed_markdown
        }"
      end

      if not_in_office_markdown.present? || updates_needed_markdown.present?
        <<~MARKDOWN
          <blockquote><details>
          <summary>Click to expand</summary>

          ```md
          #{[not_in_office_markdown, updates_needed_markdown].compact.join("\n")}
          ```
          </details></blockquote>
        MARKDOWN
      else
        ""
      end
    end

    def self.get_updates_needed(source_to_update, merged_person, contested_fields)
      updates_needed = []

      contested_fields.each do |field_name, field_data|
        source_value = field_data[:values][source_to_update]
        next if source_value.nil?

        next if values_match?(merged_person[field_name],
                              source_value)

        updates_needed << "#{
          field_name
        }: was: #{
          source_value
        }, now: #{
          merged_person[field_name]
        }"
      end

      updates_needed
    end
  end
end
