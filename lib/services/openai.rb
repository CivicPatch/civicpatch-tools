# frozen_string_literal: true

require "openai"
require "scrapers/standard"
require "scrapers/common"
require "utils/yaml_helper"
require "utils/costs_helper"
require "core/city_manager"

# TODO: track token usage
module Services
  MAX_RETRIES = 5 # Maximum retry attempts for rate limits
  BASE_SLEEP = 5  # Base sleep time for exponential backoff
  class Openai
    @@MAX_TOKENS = 100_000
    MODEL = "gpt-4o-mini"

    def initialize
      @client = OpenAI::Client.new(access_token: ENV["OPENAI_TOKEN"])
    end

    def extract_city_info(state, city_entry, content_file, city_council_url)
      content = File.read(content_file)

      return { error: "Content for city council members are too long" } if content.split(" ").length > @@MAX_TOKENS

      system_instructions, user_instructions = generate_city_info_prompt(content, city_council_url)

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]
      request_origin = "#{state}_#{city_entry["name"]}_city_scrape"
      response_yaml = run_prompt(messages, request_origin)

      response = Utils::YamlHelper.yaml_string_to_hash(response_yaml)

      # filter out invalid people
      response.select do |person|
        Scrapers::Standard.valid_name?(person["name"]) &&
          person["positions"].present? &&
          (person["phone_number"].present? || person["email"].present? || person["website"].present?)
      end

      # response.map do |person|
      #  person = Scrapers::Standard.format_person(person, city_council_url, person["website"])
      #  person
      # end
      response.map do |person|
        person["sources"] = [city_council_url]
        Scrapers::Standard.normalize_source_person(person)
      end
    end

    def extract_person_information(state, city_entry, person, content_file, url)
      positions = Core::CityManager.get_position_roles("mayor_council")
      divisions = Core::CityManager.get_position_divisions("mayor_council")
      position_examples = Core::CityManager.get_position_examples("mayor_council")

      content = File.read(content_file)
      system_instructions = <<~INSTRUCTIONS
          You are an expert data extractor.
          Extract the following properties from the provided content.
          You should be returning a YAML object with the following properties:
          You are looking for content related to #{person["name"]}
          - name
            image (Extract the image URL from the <img> tag's src attribute. This will always be a relative URL starting with images/)
            phone_number
            email
            positions (An array of strings)
            start_term_date (string. The date the person started their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
            end_term_date (string. The date the person ended their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)

        Notes:
        - Extract only the contact information associated with the person. Do not return general info.
        - Return the results in YAML format.
        - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
        - start_term_date and end_term_date should be strings.
        - For the "positions" field, split the positions into an array of strings.
          The main positions we are interested in are #{positions.join(", ")}
          Positions may also be associated with titles like #{divisions.join(", ")}
          where the positions are attached with vairous numbers or words.
          Preserve non-numeric names as they are.
          Do not list previous positions if their terms have ended.
          Examples:
          #{position_examples}
      INSTRUCTIONS

      user_instructions = <<~USER
        Here is the content:
        #{content}
      USER

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]

      request_origin = "#{state}_#{city_entry["name"]}_person_scrape"
      response = run_prompt(messages, request_origin)

      person = Utils::YamlHelper.yaml_string_to_hash(response)
      person["website"] = url

      Scrapers::Standard.normalize_source_person(person)
    end

    def generate_city_info_prompt(content, city_council_url)
      positions = Core::CityManager.get_position_roles("mayor_council")
      divisions = Core::CityManager.get_position_divisions("mayor_council")
      position_examples = Core::CityManager.get_position_examples("mayor_council")

      # System instructions: approximately 340
      system_instructions = <<~INSTRUCTIONS
        You are an expert data extractor.
        Extract the following properties from the provided content.
        Identify all people who are part of the city's mayor-council government.
        The main positions we are interested in are: #{positions.join(", ")}

        They might have other associated positions that look like these:
        #{divisions.join(",")}

        There should be an array of the following properties.
        - name
          image (Extract the image URL from the <img> tag's src attribute.#{" "}
                This will always be a relative URL starting with images/)
          phone_number: <string> Format: (123) 456-7890
          email
          positions (an array of strings)
          start_term_date (string. The date the person started their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
          end_term_date (string. The date the person ended their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
          website (Provide the absolute URL.)
                If no specific website is provided, leave this empty —#{" "}
                do not default to the general city or council page.

        Basic rules:
        - Students are NOT city council members.
        - Extract only the contact information associated with the person. Do not return general info.
        - City council members and city leaders should all be human beings with a name and at least one piece of contact field.
        - If you find just a list of names, with at least a website or email, they are likely to be council members.
        - If the content is a press release, do not extract any people data from the content.
        - Output the results in YAML format. For any fields not provided in the content, return an empty string, except for 'name' which is required.
        - If you cannot find any relevant information, return YAML as empty array.

        - To make it on the people list, they must be associated with either "position" OR "position_misc)
        - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
          They should be strings.
        - For the "positions" field, split the positions into an array of strings.#{" "}
          Preserve non-numeric names as they are.
          Do not list previous positions if their terms have ended.
          People can have multiple positions and roles.
          Examples:
          #{position_examples}
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

    def run_prompt(messages, request_origin)
      retry_attempts = 0
      response = @client.chat(
        parameters: {
          model: MODEL,
          messages: messages,
          temperature: 0.0
        }
      )

      input_tokens_num = response.dig("usage", "prompt_tokens")
      output_tokens_num = response.dig("usage", "completion_tokens")
      Utils::CostsHelper.log_llm_cost(request_origin, "openai", input_tokens_num, output_tokens_num, MODEL)

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
  end
end
