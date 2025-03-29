# frozen_string_literal: true

require "openai"
require "scrapers/standard"
require "scrapers/common"

# TODO: track token usage
module Services
  class Openai
    @@MAX_TOKENS = 100_000

    def initialize
      @client = OpenAI::Client.new(access_token: ENV["OPENAI_TOKEN"])
    end

    def extract_city_info(content_file, city_council_url)
      content = File.read(content_file)

      return { error: "Content for city council members are too long" } if content.split(" ").length > @@MAX_TOKENS

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
        Scrapers::Standard.valid_name?(person["name"]) &&
          (person["position"].present? || person["position_misc"].present?) &&
          (person["phone_number"].present? || person["email"].present? || person["website"].present?)
      end

      response["people"] = response["people"].map do |person|
        person = Scrapers::Standard.format_person(person)
        person
      end

      response
    end

    def extract_person_information(content_file)
      content = File.read(content_file)
      system_instructions = <<~INSTRUCTIONS
        You are an expert data extractor.
        Extract the following properties from the provided content
        - name
        - position (Strictly mayor, council_president, or council_member. Leave blank if not found)
        - position_misc (An array of strings, if available)
        - phone_number
        - image (Extract the image URL from the <img> tag's src attribute. This will always be a relative URL starting with images/)
        - email
        - start_term_date (The date the person started their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
        - end_term_date (The date the person ended their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)

      Notes: 
      - Return the results in YAML format.
      - If the content is not a person, YAML with the key "error" and the value "Not a person".
      - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
        can be directly inferred with certainty—do not assume or estimate missing information.
      - For "position_misc", convert the following ambiguous position titles into a structured YAML format. 
        Preserve non-numeric names as they are.
        For titles like "city attorney" or "city clerk",
        categorize them under `type: "role"` with the role name as the value.
        Examples:

        Input: "ward 3" → Output: `{ type: "ward", value: "3" }`
        Input: "ward #3" → Output: `{ type: "ward", value: "3" }`
        Input: "position #5" → Output: `{ type: "position", value: "5" }`
        Input: "5th position" → Output: `{ type: "position", value: "5" }`
        Input: "district 8" → Output: `{ type: "district", value: "8" }`
        Input: "district blue" → Output: `{ type: "district", value: "blue" }`
        Input: "blue district" → Output: `{ type: "district", value: "blue" }`
        Input: "alumnus ward" → Output: `{ type: "ward", value: "alumnus" }`
        Input: "city attorney" → Output: `{ type: "role", value: "city attorney" }`
        Input: "city clerk" → Output: `{ type: "role", value: "city clerk" }`
        Input: "position 5" → Output: `{ type: "position", value: "5" }`
        Input: "seat 5" → Output: `{ type: "seat", value: "5" }`
        Input: "council vice president" → Output: `{ type: "role", value: "council vice president" }`
      INSTRUCTIONS

      user_instructions = <<~USER
        Here is the content:
        #{content}
      USER

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]

      response = run_prompt(messages)
      response = response_to_yaml(response)

      # TODO: handle errors
      return nil if response["error"].present?

      Scrapers::Standard.format_person(response)
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
              - position (Strictly mayor, council_president, or council_member. Leave blank if not found)
              - position_misc (An array of strings, if available)
              - phone_number
              - image (Extract the image URL from the <img> tag's src attribute. This will always be a relative URL starting with images/)
              - email
              - website (Provide the absolute URL.)
                If no specific website is provided, leave this empty — do not default to the general city or council page.)
              - start_term_date (The date the person started their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
              - end_term_date (The date the person ended their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)

        Basic rules:
        - Youth council members are NOT city council members.
        - City council members and city leaders should all be human beings with a name and at least one piece of contact field.
        - If you find just a list of names, with at least a website or email, they are likely to be council members.
        - If the content is a press release, do not extract any people data from the content.
        - Output the results in YAML format. For any fields not provided in the content, return an empty string, except for 'name' which is required.
        - If you cannot find any relevant information, return the following YAML:
          - error: "No relevant information found"
        - To make it on the people list, they must be associated with either "position" OR "position_misc)
        - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
        - For "position_misc", convert the following ambiguous position titles into a structured YAML format.
          Preserve non-numeric names as they are. 
          For titles like "city attorney" or "city clerk", 
          categorize them under `type: "role"` with the role name as the value.
          Examples:
          Input: "ward 3" → Output: `{ type: "ward", value: "3" }`
          Input: "ward #3" → Output: `{ type: "ward", value: "3" }`
          Input: "position #5" → Output: `{ type: "position", value: "5" }`
          Input: "5th position" → Output: `{ type: "position", value: "5" }`
          Input: "district 8" → Output: `{ type: "district", value: "8" }`
          Input: "district blue" → Output: `{ type: "district", value: "blue" }`
          Input: "blue district" → Output: `{ type: "district", value: "blue" }`
          Input: "alumnus ward" → Output: `{ type: "ward", value: "alumnus" }`
          Input: "city attorney" → Output: `{ type: "role", value: "city attorney" }`
          Input: "city clerk" → Output: `{ type: "role", value: "city clerk" }`

        Example Output (YAML):
        ---
        people:
          - name: "Jane Smith"
            position: council_member
            position_misc:
              - type: "seat"
                value: "1"
            phone_number: "555-123-4567"
            image: "images/smith.jpg"
            email: "jsmith@cityofexample.gov"
            website: "https://www.cityofexample.gov/council/smith"
          - name: "John Doe"
            position_misc:
              - type: "ward"
                value: "3"
            phone_number: ""
            image: ""
            email: ""
            website: "/council/doe"
          - name: "Robert Johnson"
            position: mayor
            phone_number: "555-111-2222"
            image: "images/mayor.jpg"
            email: "mayor@cityofexample.gov"
            website: "https://www.cityofexample.gov/mayor"
            position_misc:
              - type: "role"
                value: "city_attorney"

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
