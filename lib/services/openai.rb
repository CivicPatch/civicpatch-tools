# frozen_string_literal: true

require "openai"
require "scrapers/standard"

# TODO: track token usage
module Services
  class Openai
    @@MAX_TOKENS = 100_000

    def initialize
      @client = OpenAI::Client.new(access_token: ENV["OPENAI_TOKEN"])
    end

    def extract_city_division_map_data(state, city, division_type, geojson_file_path, url)
      truncated_geojson = extract_simplified_geojson(geojson_file_path)
      truncated_geojson_text = truncated_geojson.to_json

      system_instructions = <<~INSTRUCTIONS
        You are an expert data extractor. The following is #{truncated_geojson.length} of the features of a geojson file.
        Determine if the following content contains #{truncated_geojson.length} city council #{division_type}s.

        If available, determine the following properties strictly in YAML format:
        - has_division_data ("true" or "false" -- true if the data set has the city's #{division_type} info)
        - has_city_data ("true" or "false" -- true if based off the page url and the data, that the dataset is for #{city}, #{state})
      INSTRUCTIONS

      user_instructions = <<~USER
        * This is the data: #{truncated_geojson_text}.
        * The city is split into #{division_type}s, and are more generically called "wards" or "districts".
        * The page url is: #{url}
        * Return the results in YAML format.

      USER

      if system_instructions.split(" ").length + user_instructions.split(" ").length > @@MAX_TOKENS
        raise "Extract city division map data: system instructions and user instructions are too long"
      end

      puts "system_instructions: #{system_instructions}"
      puts "user_instructions: #{user_instructions}"

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]

      response = run_prompt(messages)
      response_to_yaml(response)
    end

    def extract_city_info(_state, _city, content_file, city_council_url)
      content = File.read(content_file)

      return { error: "Content for city council members is too long" } if content.split(" ").length > @@MAX_TOKENS

      system_instructions, user_instructions = generate_city_info_prompt(content, city_council_url)

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]
      response_yaml = run_prompt(messages)

      response = response_to_yaml(response_yaml)

      return response if response["error"].present?

      # filter out invalid people
      response["people"] = response["people"].select do |person|
        person["name"].present? &&
          (person["position"].present? || person["position_misc"].present?) &&
          (person["phone_number"].present? || person["email"].present? || person["website"].present?)
      end

      response["people"].map do |person|
        person["phone_number"] = Scrapers::Standard.format_phone_number(person["phone_number"])

        # Determine position/position_misc
        next unless person["position_misc"].present?

        person["position_misc"] = person["position_misc"].downcase.gsub(/[ .]+/, "_")
        person["position_misc"] = "" if %w[member chair].include?(person["position_misc"])

        person["position"] = "council_member" if council_member_position?(person["position"], person["position_misc"])
      end

      response
    end

    def response_to_yaml(response_content)
      # Extract YAML content from the response
      # If the response is wrapped in ```yaml ... ``` or similar, extract just the YAML content
      yaml_content = if response_content.match?(/```(?:yaml|yml)?\s*(.*?)```/m)
                       response_content.match(/```(?:yaml|yml)?\s*(.*?)```/m)[1]
                     else
                       response_content
                     end

      YAML.load(yaml_content)
    end

    def generate_city_info_prompt(content, city_council_url)
      # System instructions: approximately 340
      system_instructions = <<~INSTRUCTIONS
        You are an expert data extractor.
        Extract the following properties from the provided content:

        For each city leader or council member (leave empty if not found):
          - people:
              - name
              - position (Strictly mayor, council_president, or council_member)
              - position_misc (Can be loosely interpreted, if available - Examples: position_2, district_3, city_attorney, seat_4, etc.)
              - phone_number
              - image (Extract the image URL from the <img> tag's src attribute. This will always be a relative URL.)
              - email
              - website (Provide the absolute URL.)
                If no specific website is provided, leave this empty — do not default to the general city or council page.)

        Basic rules:
        - Youth council members are NOT city council members.
        - City council members and city leaders should all be human beings with a name and at least one piece of contact field.
        - If you find just a list of names, with at least a website or email, they are likely to be council members.
        - If the content is a press release, do not extract any people data from the content.
        - Output the results in YAML format. For any fields not provided in the content, return an empty string, except for 'name' which is required.
        - If you cannot find any relevant information, return the following YAML:
          - error: "No relevant information found"
        - To make it on the people list, they must be associated with either "position" OR "position_misc)

        Example Output (YAML):
        ---
        people:
          - name: "Jane Smith"
            position: council_member
            phone_number: "555-123-4567"
            image: "images/smith.jpg"
            email: "jsmith@cityofexample.gov"
            website: "https://www.cityofexample.gov/council/smith"
          - name: "John Doe"
            position_misc: city_attorney
            phone_number: ""
            image: ""
            email: ""
            website: "/council/doe"
          - name: "Robert Johnson"
            position: "mayor"
            phone_number: "555-111-2222"
            image: "images/mayor.jpg"
            email: "mayor@cityofexample.gov"
            website: "https://www.cityofexample.gov/mayor"

      INSTRUCTIONS

      content = <<~CONTENT
        #{content}
      CONTENT

      # User instructions: approximately 40 tokens (excluding the HTML content)
      user_instructions = <<~USER
        The page URL is: #{city_council_url}
        Here is the content:
        #{content}
      USER

      [system_instructions, user_instructions]
    end

    private

    def run_prompt(messages)
      response = @client.chat(
        parameters: {
          model: "gpt-4o-mini",
          # model: "gpt-3.5-turbo",
          messages: messages,
          temperature: 0.0
        }
      )

      response.dig("choices", 0, "message", "content")
    end

    # Remove coordinates from geojson file
    def extract_simplified_geojson(geojson_file_path)
      file_size_mb = File.size(geojson_file_path) / 1024.0 / 1024.0
      puts "Loading geojson file - #{file_size_mb} MB"

      json_data = JSON.parse(File.read(geojson_file_path))

      json_data["features"][0, 3].map do |feature|
        {
          type: feature["type"],
          properties: feature["properties"]
        }
      end
    end

    def council_member_position?(position, position_misc)
      position.blank? && keywords_present?(position_misc)
    end

    def keywords_present?(position_misc)
      keywords = %w[position seat district ward]
      keywords.any? { |keyword| position_misc.include?(keyword) }
    end
  end
end
