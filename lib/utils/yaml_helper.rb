module Utils
  class YamlHelper
    def self.yaml_string_to_hash(yaml_string)
      clean_yaml_string = yaml_string.gsub(/\A```yaml\n/, "").gsub(/\n```\z/, "") # Remove YAML code block markers if present
      parsed_data = YAML.safe_load(clean_yaml_string, permitted_classes: [Date])

      # A function to format Date objects
      format_date = ->(value) { value.is_a?(Date) ? value.strftime("%Y-%m-%d") : value }

      case parsed_data
      when Hash
        parsed_data.transform_values(&format_date)
      when Array
        parsed_data.map do |element|
          element.is_a?(Hash) ? element.transform_values(&format_date) : element
        end
      else
        parsed_data
      end
    end
  end
end
