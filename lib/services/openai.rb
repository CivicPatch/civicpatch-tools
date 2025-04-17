# frozen_string_literal: true

require "openai"
require "scrapers/standard"
require "scrapers/common"
require "services/shared/response_schemas"
require "utils/costs_helper"
require "core/city_manager"

# TODO: track token usage
module Services
  MAX_RETRIES = 5 # Maximum retry attempts for rate limits
  BASE_SLEEP = 5  # Base sleep time for exponential backoff
  class Openai
    @@MAX_TOKENS = 100_000
    MODEL = "gpt-4.1-mini"

    def initialize
      @client = OpenAI::Client.new(access_token: ENV["OPENAI_TOKEN"])
    end

    def extract_city_people(state, city_entry, government_type, content_file, page_url)
      content = File.read(content_file)

      return { error: "Content for city council members are too long" } if content.split(" ").length > @@MAX_TOKENS

      system_instructions, user_instructions = generate_city_info_prompt(government_type, content, page_url)

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]
      request_origin = "#{state}_#{city_entry["name"]}_city_scrape"
      response = run_prompt(messages, request_origin)

      return nil if response.blank?

      # filter out invalid people
      people = response["people"].select do |person|
        Scrapers::Standard.valid_name?(person["name"]) &&
          person["positions"].present?
      end

      people.map do |person|
        Services::Shared::People.format_raw_data(person, page_url)
      end
    end

    def generate_city_info_prompt(government_type, content, page_url)
      positions = Core::CityManager.get_position_roles(government_type)
      divisions = Core::CityManager.get_position_divisions(government_type)
      position_examples = Core::CityManager.get_position_examples(government_type)
      current_date = Date.today.strftime("%Y-%m-%d")

      # System instructions: approximately 340
      system_instructions = <<~INSTRUCTIONS
        You are an expert data extractor.

        First, determine if the content contains elected officials' information. 
        If not, return an empty array.

        Key roles: #{positions.join(", ")}
        Associated divisions: #{divisions.join(",")}
        Examples: #{position_examples}

        Return a JSON object with people, each having:
        - name: Full name only (not titles)
        - image: URL from <img> tag (starting with "images/")
        - phone_number: {data, llm_confidence, llm_confidence_reason, proximity_to_name, markdown_formatting: {in_list}}
        - email: {data, llm_confidence, llm_confidence_reason, proximity_to_name, markdown_formatting: {in_list}}
        - website: {data, llm_confidence, llm_confidence_reason, proximity_to_name, markdown_formatting: {in_list}}
        - term_date: {data, llm_confidence, llm_confidence_reason, proximity_to_name, markdown_formatting: {in_list}}
        - positions: [array of strings]

        Format example:
        {
          "people": [
            {
              "name": "John Doe",
              "image": "images/12341324132.jpg",
              "phone_number": {"data": "123-456-7890", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under Contact.", "proximity_to_name": 50, "markdown_formatting": {"in_list": true}},
              "email": {"data": "john.doe@example.com", "llm_confidence": 0.95, "llm_confidence_reason": "Directly associated with name.", "proximity_to_name": 10, "markdown_formatting": {"in_list": false}},
              "website": {"data": "https://example.com/john-doe", "llm_confidence": 0.95, "llm_confidence_reason": "Found under header", "markdown_formatting": {"in_list": true}},
              "positions": ["Mayor", "Council Member"],
              "term_date": {"data": "2022-01-01 to 2022-12-31", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under header.", "proximity_to_name": 35, "markdown_formatting": {"in_list": true}}
            }
          ]
        }

        Guidelines:
        - For "llm_confidence": Use 0-1 scale with reason for your confidence
        - For "proximity_to_name": Word count distance between info and person's name
        - Extract only person-specific information, not general contact info
        - IMPORTANT: DO NOT extract phone numbers or emails labeled as belonging to "Legislative Assistant", "Staff", "Office", or any other support personnel.
        - DO NOT extract contact information if you are less than 90% confident it belongs directly to the person.
        - Omit missing fields except for "name"
        - For positions: Include only active roles (today is #{current_date})
        - Name extraction: Extract full names ONLY, not titles
          - CORRECT: "Lisa Brown" (not "Mayor Brown" or "Mayor Lisa Brown")
          - Titles belong in positions array, not in names
        - Website extraction:
          - Prioritize person-specific pages over landing pages
          - Consider links associated with names/photos
          - Prefer deeper paths and "/about" pages when available
        - For email, phone_number, term_date extraction:
          - Only extract contact information if it is CLEARLY for the specific person or their office.
          - If contact information is more than 30 words away from the person's name, DO NOT include it unless:
            - It appears in a section that is clearly dedicated to that person's contact information.
        - For phone_number:
          - If there are multiple phone numbers, extract the primary one.
      INSTRUCTIONS

      content = <<~CONTENT
        #{content}
      CONTENT

      user_instructions = <<~USER
        The page URL is: #{page_url}
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
          temperature: 0.0,
          response_format: { type: "json_object" }
        }
      )

      input_tokens_num = response.dig("usage", "prompt_tokens")
      output_tokens_num = response.dig("usage", "completion_tokens")
      Utils::CostsHelper.log_llm_cost(request_origin, "openai", input_tokens_num, output_tokens_num, MODEL)

      json_output = response.dig("choices", 0, "message", "content")

      begin
        JSON.parse(json_output)
      rescue StandardError
        nil
      end
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
      # rescue Faraday::BadRequestError => e
      #  puts "[400] Bad request. #{e.message} #{e.backtrace}"
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
