module GitHub
  class CityPeople
    def self.to_markdown_table(contested_fields)
      # Initialize the header for the table
      source_names = contested_fields.map { |_, field_data| field_data[:values].keys }.flatten.uniq

      headers = ["Field", "Disagreement Score"] + source_names
      table = []

      contested_fields.each do |field, field_data|
        row = [
          field.to_s.capitalize, # Capitalize the field name
          field_data[:disagreement_score].round(2) # Disagreement score
        ]

        # For each field, display all of the contested values or an empty cell in each column
        contested_values = source_names.map do |source_name|
          field_data[:values][source_name]
        end

        contested_values.each do |value|
          row << if value.is_a?(Array)
                   value.join(", ")
                 else
                   value
                 end
        end

        # Add the row to the table
        table << row
      end

      # Now build the markdown table string
      markdown = "| #{headers.join(" | ")} |"
      separator_line = "| #{headers.map { |header| "-" * header.length }.join(" | ")} |"
      markdown += "\n#{separator_line}"
      table.each do |row|
        markdown += "\n| #{row.join(" | ")} |" # Add the data rows
      end

      markdown
    end
  end
end
