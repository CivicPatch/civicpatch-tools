# frozen_string_literal: true

require "openai"
require "scrapers/standard"
require "scrapers/common"

# TODO: track token usage
module Services
  MAX_RETRIES = 5 # Maximum retry attempts for rate limits
  BASE_SLEEP = 2  # Base sleep time for exponential backoff
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
      response = format_yaml_content(response_yaml)

      return response if response["error"].present?

      # filter out invalid people
      response["people"] = response["people"].select do |person|
        Scrapers::Standard.valid_name?(person["name"]) &&
          person["positions"].present? &&
          (person["phone_number"].present? || person["email"].present? || person["website"].present?)
      end

      response["people"] = response["people"].map do |person|
        person = Scrapers::Standard.format_person(person, city_council_url, person["website"])
        person
      end

      response
    end

    def extract_person_information(content_file, url)
      positions = ["council member", "council president", "council vice president", "mayor"]

      content = File.read(content_file)
      system_instructions = <<~INSTRUCTIONS
          You are an expert data extractor.
          Extract the following properties from the provided content
          - name
          - image (Extract the image URL from the <img> tag's src attribute. This will always be a relative URL starting with images/)
          - phone_number
          - email
          - positions (An array of objects, if available)
          - start_term_date (string. The date the person started their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
          - end_term_date (string. The date the person ended their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)

        Notes:
        - Extract only the contact information associated with the person. Do not return general info.
        - Return the results in YAML format.
        - If the content is not a person, YAML with the key "error" and the value "Not a person".
        - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
        - start_term_date and end_term_date should be strings.
        - For "positions", convert the following ambiguous position titles into a structured YAML format.#{" "}
          Preserve non-numeric names as they are.
          The main positions we are interested in are #{positions.join(", ")}.
          Do not list previous positions if their terms have ended.
          For titles like "city attorney" or "city clerk",
          categorize them under `type: "role"` with the role name as the value.
          People can have multiple positions and roles.
          Examples:

          Input: "council member ward 3" → Output: `[{ type: "role", value: "council member" }, { type: "ward", value: "3" }]`
          Input: "ward #3" → Output: `[{ type: "ward", value: "3" }]`
          Input: "3rd district" → Output: `[{ type: "ward", value: "3" }]`
          Input: "seat 5" → Output: `[{ type: "role", value: "council member" }, { type: "seat", value: "5" }]`
          Input: "council vice president" → Output: `[{ type: "role", value: "council vice president" }]`
          Input: "mayor" → Output: `[{ type: "role", value: "mayor" }]`
          Input: "mayor position 7" → Output: `[{ type: "role", value: "mayor" }, { type: "position", value: "7" }]`
          Input: "council president" → Output: `[{ type: "role", value: "council president" }]`
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

      response = format_yaml_content(response)

      # TODO: handle errors
      return nil if response["error"].present?

      Scrapers::Standard.format_person(response, url)
    end

    def generate_city_info_prompt(content, city_council_url)
      positions = ["council member", "council president", "council vice president", "mayor"]
      # System instructions: approximately 340
      system_instructions = <<~INSTRUCTIONS
        You are an expert data extractor.
        Extract the following properties from the provided content:

        For each city leader or council member (leave empty if not found):
          - people:
              - name
              - image (Extract the image URL from the <img> tag's src attribute. This will always be a relative URL starting with images/)
              - phone_number
              - email
              - positions (an array of objects, if available)
              - start_term_date (string. The date the person started their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
              - end_term_date (string. The date the person ended their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
              - website (Provide the absolute URL.)
                If no specific website is provided, leave this empty — do not default to the general city or council page.)

        Basic rules:
        - Students are NOT city council members.
        - Extract only the contact information associated with the person. Do not return general info.
        - City council members and city leaders should all be human beings with a name and at least one piece of contact field.
        - If you find just a list of names, with at least a website or email, they are likely to be council members.
        - If the content is a press release, do not extract any people data from the content.
        - Output the results in YAML format. For any fields not provided in the content, return an empty string, except for 'name' which is required.
        - If you cannot find any relevant information, return the following YAML:
          - error: "No relevant information found"
        - To make it on the people list, they must be associated with either "position" OR "position_misc)
        - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
          They should be strings.
        - For "positions", convert the following ambiguous position titles into a structured YAML format.
          Preserve non-numeric names as they are.#{" "}
          The main positions we are interested in are #{positions.join(", ")}.
          Do not list previous positions if their terms have ended.
          For titles like "city attorney" or "city clerk",#{" "}
          categorize them under `type: "role"` with the role name as the value.
          People can have multiple positions and roles.
          Examples:
          Input: "council member ward 3" → Output: `[{ type: "role", value: "council member" }, { type: "ward", value: "3" }]`
          Input: "ward #3" → Output: `[{ type: "ward", value: "3" }]`
          Input: "3rd district" → Output: `[{ type: "ward", value: "3" }]`
          Input: "seat 5" → Output: `[{ type: "role", value: "council member" }, { type: "seat", value: "5" }]`
          Input: "council vice president" → Output: `[{ type: "role", value: "council vice president" }]`
          Input: "mayor" → Output: `[{ type: "role", value: "mayor" }]`
          Input: "mayor position 7" → Output: `[{ type: "role", value: "mayor" }, { type: "position", value: "7" }]`
          Input: "council president" → Output: `[{ type: "role", value: "council president" }]

        Example Output (YAML):
        ---
        people:
          - name: "Jane Smith"
            positions:
              - type: "role"
                value: "council member"
              - type: "position"
                value: "5"
            phone_number: "555-123-4567"
            image: "images/smith.jpg"
            email: "jsmith@cityofexample.gov"
            website: "https://www.cityofexample.gov/council/smith"
          - name: "John Doe"
            positions:
              - type: "role"
                value: "council member"
              - type: "ward"
                value: "3"
            phone_number: ""
            image: ""
            email: ""
            website: "/council/doe"
          - name: "Robert Johnson"
            positions:
              - type: "role"
                value: "mayor"
              - type: "role"
                value: "council member"
              - type: "position"
                value: "1"
            phone_number: "555-111-2222"
            image: "images/mayor.jpg"
            email: "mayor@cityofexample.gov"
            website: "https://www.cityofexample.gov/mayor"
            start_term_date: "2020-01-01"
            end_term_date: "2025-12-31"

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
      retry_attempts = 0
      response = @client.chat(
        parameters: {
          model: "gpt-4o-mini",
          messages: messages,
          temperature: 0.0
        }
      )

      response.dig("choices", 0, "message", "content")
    rescue Faraday::TooManyRequestsError => e
      if retry_attempts < MAX_RETRIES
        sleep_time = BASE_SLEEP**retry_attempts + rand(0..1) # Exponential backoff with jitter
        puts "[429] Rate limited. Retrying in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
        sleep sleep_time
        retry_attempts += 1
        retry
      else
        puts "[429] Too many requests. Max retries reached for #{url}."
      end
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

    def format_yaml_content(response_content)
      # Extract YAML content from code blocks if present
      content = response_content.match(/```(?:yaml|yml)?\s*(.*?)```/m)&.[](1) || response_content

      # Ensure content starts with YAML document marker
      content = "---\n#{content}" unless content.start_with?("---")

      # Remove any trailing whitespace and ensure ending newline
      content = "#{content.strip}\n"

      YAML.safe_load(content, permitted_classes: [])
    end

    def make_openai_request(client, messages, retries: 3, timeout: 60)
      Timeout.timeout(timeout) do
        client.chat(
          parameters: {
            model: "gpt-4", # or whatever model you're using
            messages: messages,
            temperature: 0.7
          }
        )
      end
    rescue Timeout::Error, Faraday::TimeoutError, Net::ReadTimeout => e
      raise "OpenAI request failed after multiple retries: #{e.message}" unless retries > 0

      puts "OpenAI request timed out. Retrying... (#{retries} attempts left)"
      sleep(2) # Wait 2 seconds before retry
      retries -= 1
      retry
    end
  end
end
