# frozen_string_literal: true

require "openai"
require "services/shared/response_schemas"
require "utils/costs_helper"
require "utils/name_helper"
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

    def extract_city_people(municipality_context, content_file, page_url, person_name = "")
      state = municipality_context[:state]
      municipality_entry = municipality_context[:municipality_entry]
      government_type = municipality_context[:government_type]

      content = File.read(content_file)

      return { error: "Content for city council members are too long" } if content.split(" ").length > @@MAX_TOKENS

      system_instructions, user_instructions = generate_city_info_prompt(government_type, content, page_url,
                                                                         person_name)

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]
      request_origin = "#{state}_#{municipality_entry["name"]}_city_scrape"
      response = run_prompt(messages, request_origin)

      return nil if response.blank?

      # filter out invalid people
      people = response["people"].select do |person|
        Utils::NameHelper.valid_name?(person["name"])
      end

      people.map do |person|
        Services::Shared::People.format_raw_data(person, page_url)
      end
    end

    def generate_city_info_prompt(government_type, content, page_url, person_name = "")
      positions = Core::CityManager.get_position_roles(government_type)
      divisions = Core::CityManager.get_position_divisions(government_type)
      position_examples = Core::CityManager.get_position_examples(government_type)
      current_date = Date.today.strftime("%Y-%m-%d")

      content_type = if person_name.present?
                       "First, determine if the content contains information about the target person."
                     else
                       "First, determine if the content contains a directory of elected officials."
                     end

      # System instructions: approximately 340
      system_instructions = <<~INSTRUCTIONS
        You are an expert data extractor.

        #{content_type}#{" "}
        If not, return an empty array.

        #{person_name.present? ? "Target Person: #{person_name}" : ""}
        Key roles: #{positions.join(", ")}
        Associated divisions: #{divisions.join(",")}
        Examples: #{position_examples}

        Return a JSON object with people, each having:
        - name: Full name only (not titles)
        - positions: [array of strings]
        - image: String, URL from markdown image: (starting with "images/")
        - phone_number: {data, llm_confidence, llm_confidence_reason }
        - email: {data, llm_confidence, llm_confidence_reason }
        - website: {data, llm_confidence, llm_confidence_reason }
        - start_date: {data, llm_confidence, llm_confidence_reason }
        - end_date: {data, llm_confidence, llm_confidence_reason }

        Format example:
        {
          "people": [
            {
              "name": "John Doe",
              "positions": ["Mayor", "Council Member"],
              "image": "images/john-doe.jpg",
              "phone_number": {"data": "123-456-7890", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under Contact."},
              "email": {"data": "john.doe@example.com", "llm_confidence": 0.95, "llm_confidence_reason": "Directly associated with name."},
              "website": {"data": "https://example.com/john-doe", "llm_confidence": 0.95, "llm_confidence_reason": "Found under header"},
              "start_date": {"data": "2022-01-01", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under header."},
              "end_date": {"data": "2022-12-31", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under header."}
            }, {
              "name": "Jane Smith",
              "phone_number": {"data": "(987) 654-3210", "llm_confidence": 0.90, "llm_confidence_reason": "Extracted from markdown link text like [(987) 654-3210]()"},
              "email": {"data": "jane.smith@example.gov", "llm_confidence": 0.92, "llm_confidence_reason": "Found under 'Contact Us' section near name."},
              "positions": ["Council President"],
              "end_date": {"data": "2022-12-31", "llm_confidence": 0.95, "llm_confidence_reason": "Found phrase 'Term Expires December 31, 2027'"}
            }
          ]
        }

        Guidelines:
        - For "llm_confidence": Use 0-1 scale with reason for your confidence
        - Extract only person-specific information, not general contact info
        - Image selection:
          - Find the image URL most closely associated with the person, preferably
            appearing immediately near or directly following the person's name or biography heading in the text.
          - Prioritize portraits or headshots. IGNORE logos, icons, banners,
            or images with alt text like "Loading", "Logo", "Icon", "Search", "Banner".
          - Check the image's alt text (e.g., `![Alt text](image.jpg)`) for clues#{" "}
            like the person's name, but prioritize proximity and portrait style to the person's name.
        - DO NOT extract contact information if you are less than 90% confident it belongs directly to the person.
        - Omit missing fields except for "name"
        - For positions:#{" "}
          - Include only active roles (today is #{current_date}).
          - Include both roles and divisions, where available.
        - Name extraction: Extract full names ONLY, not titles
          - CORRECT: "Lisa Brown" (not "Mayor Brown" or "Mayor Lisa Brown")
          - Titles belong in positions array, not in names
        - Website extraction:
          - Goal: Find the primary, stable profile or biography page for the person.
          - Prioritize person-specific pages over landing pages (e.g., `/council/john-doe` over `/council/`).
          - Consider links associated with names/photos
          - Prefer deeper paths and "/about" pages when available
        - For email, phone_number, start_date and end_date extraction:
          - Only extract contact information if it is CLEARLY for the specific person or their office.
          - If contact information is more than 30 words away from the person's name, DO NOT include it unless:
            - It appears in a section that is clearly dedicated to that person's contact information.
        - For phone_number:
          - Format: (123) 456-7890 or null
          - If there are multiple phone numbers, extract the primary one.
        - start_date and end_date extraction:
          - Format: YYYY, YYYY-MM-DD or null
          - IMPORTANT: Carefully search for explicit start dates and end dates using these common patterns:
            - Start date patterns: 'Term Began:', 'Elected:', 'Sworn In:', 'Appointed:', 'Serving Since:', 'First Elected:'
            - Also look for these start date variations: 'Elected in', 'Took Office', 'Started', 'Since', 'Beginning', 'Commenced', 'Assumed Office', 'Joined Council', 'Began Service'
            - End date patterns: 'Term Expires:', 'Term Ends:', 'Serving Until:', 'Until:', 'Next Election:'
          - Additional start date examples:
            - "Term Began: 2024" → start_date: "2024"
            - "Elected in November 2022" → start_date: "2022-11-01"
            - "Took office January 2023" → start_date: "2023-01-01"
            - "Serving since 2021" → start_date: "2021-01-01"
          - Examples of complete date extraction:
            - "Elected: January 2023" → start_date: "2023-01-01"
            - "Term expires December 2026" → end_date: "2026-12-31"
            - "Term: 2024-2028" → start_date: "2024-01-01", end_date: "2028-12-31"
            - "Elected 2020, Term expires 2024" → start_date: "2020-01-01", end_date: "2024-12-31"#{" "}
          - If ONLY a year is given for the *entire term* (e.g., 'Term: 2024'), set start_date to YYYY-01-01 and end_date to YYYY-12-31.
          - If only a start year is given (e.g., 'Elected 2023'), set start_date (using YYYY) and set end_date to null.
          - If only an end year is given (e.g., 'Term Expires 2027'), set end_date (using YYYY) and set start_date to null.
          - CRITICAL: If a start or end date is not explicitly mentioned or derivable *only* from the year rules above,
            do not include it in the response.
          - If multiple terms are listed, extract only the current or most recent term.
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
