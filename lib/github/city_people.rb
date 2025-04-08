module GitHub
  class CityPeople
    def self.to_markdown_table(contested_fields, merged_person)
      puts "merged_person: #{merged_person.inspect}"
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
  end
end
