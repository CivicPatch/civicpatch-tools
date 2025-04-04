module GitHub
  class CityPeople
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
