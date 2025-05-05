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

      content = File.read(content_file)

      return { error: "Content for city council members are too long" } if content.split(" ").length > @@MAX_TOKENS

      system_instructions, user_instructions = generate_city_info_prompt(municipality_context, content, page_url,
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

    def generate_city_info_prompt(municipality_context, content, page_url, person_name = "")
      state = municipality_context[:state]
      government_type = municipality_context[:government_type]
      positions = Core::CityManager.get_position_roles(government_type)
      divisions = Core::CityManager.get_position_divisions(government_type)
      position_examples = Core::CityManager.get_position_examples(government_type)
      municipality_entry = municipality_context[:municipality_entry]
      current_date = Date.today.strftime("%Y-%m-%d")
      maybe_target_people = municipality_context[:config]["source_directory_list"]["people"].compact.map do |person|
        person&.dig("name")
      end

      content_type = if person_name.present?
                       "First, determine if the content contains information about the target person."
                     else
                       %(Your primary task is to identify and extract information for ALL council members
                         of the target municipality found within the provided content.
                         As a helpful guide, the following people might be council members based on previous data:
                         [#{maybe_target_people.join(", ")}].
                         Use this list to aid identification, but DO NOT limit your search to only these names.
                         Extract information for EVERY relevant person you find in the content, regardless
                         of whether they were on the provided list.
                         If the content does not appear to contain council member information, return an empty JSON array `[]`.
                         )
                     end

      system_instructions = <<~INSTRUCTIONS
        You are an expert data extractor focused on accuracy.

        #{content_type} If not, return an empty JSON array `[]`.

        Target Person (if applicable): #{person_name}
        Target Municipality: #{municipality_entry["name"]}, #{state}
        Key roles: #{positions.join(", ")}
        Associated divisions: #{divisions.join(",")}
        Examples: #{position_examples}

        Return a JSON object with a key "people" containing an array. Each object represents one person and MUST include ALL fields (name, positions, image, phone_number, email, website, start_date, end_date), populating with extracted data or null.

        Output Field Definitions & Structure:
        - name: (String) Full name only (no titles).
        - positions: (Array of Strings) Active municipal roles matching targets. Include division/district.
        - image: (String or null) URL of the person's portrait/headshot (usually starts 'images/').
        - phone_number: (Object or null) {data: "Formatted Number", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}.
        - email: (Object or null) {data: "email@example.com", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}.
        - website: (Object or null) {data: "http(s)://...", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}.
        - start_date: (Object or null) {data: "YYYY" or "YYYY-MM" or "YYYY-MM-DD", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}.
        - end_date: (Object or null) {data: "YYYY" or "YYYY-MM" or "YYYY-MM-DD", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}.

        Example Format: # Shows desired output for common patterns
        {
          "people": [
            {
              "name": "Denyse McGriff",
              "positions": ["Mayor"],
              "image": "images/cf3a4400bcf8e75eb5a9cd3748d7d7ac428cb1663c701fe42b89fb1dc8933f63.jpg",
              "phone_number": {"data": "503-656-3912", "llm_confidence": 0.95, "llm_confidence_reason": "Found number labeled 'Home:' near name."},
              "email": {"data": "dmcgriff@orcity.org", "llm_confidence": 0.98, "llm_confidence_reason": "Extracted from mailto link text near name."},
              "website": {"data": "https://www.orcity.org/1772/Mayor-Denyse-McGriff", "llm_confidence": 0.9, "llm_confidence_reason": "Primary page URL."},
              "start_date": {"data": "2023-01-01", "llm_confidence": 0.99,"llm_confidence_reason": "Extracted start date from 'Term: January 1, 2023 to ...'"},
              "end_date": {"data": "2026-12-31", "llm_confidence": 0.99, "llm_confidence_reason": "Extracted end date from 'Term: ... to December 31, 2026'"}
            }, {
              "name": "Adam Marl",
              "positions": ["Commissioner"],
              "image": "images/f7ac574487389ed707b5d516d17500f55ca16e63d4b8100ef310b0d792cce875.jpg",
              "phone_number": {"data": "503-406-8165", "llm_confidence": 0.95, "llm_confidence_reason": "Found number labeled 'Cell:' near name."},
              "email": {"data": "amarl@orcity.org", "llm_confidence": 0.98, "llm_confidence_reason": "Extracted from mailto link text near name."},
              "website": {"data": "https://www.orcity.org/1775/Commissioner-Adam-Marl", "llm_confidence": 0.9, "llm_confidence_reason": "Primary page URL."},
              "start_date": {"data": "2023-01-01", "llm_confidence": 0.99,"llm_confidence_reason": "Extracted start date from 'Term: January 1, 2023 to ...'"},
              "end_date": {"data": "2026-12-31", "llm_confidence": 0.99, "llm_confidence_reason": "Extracted end date from 'Term: ... to December 31, 2026'"}
            }
          ]
        }

        Extraction Guidelines:
        - General: Today is #{current_date}. Merge details for the same person. Assign confidence (0-1 scale) + brief reason for each field's data.
        - Name: Extract full names ONLY (e.g., "Denyse McGriff", not "Mayor Denyse McGriff"). Titles go in 'positions'.
        - Positions: Extract ONLY active roles matching Target Roles/Examples (municipal legislative/executive). EXCLUDE judicial, most admin staff, non-municipal.
        - Image: Extract URL of portrait/headshot near name. Ignore logos, banners, icons. Check alt text but prioritize proximity/style. URL should usually start 'images/'.
        - Contact Details (Phone/Email/Website):
          - Associate details logically if near the person's name/section.
          - Phone Prefixes: Extract number after labels like "Office:", "Cell:", "Mobile:", "Direct:", "Home:". Exclude "Fax:". Format numbers simply.
          - Markdown Links: Extract email/phone from the VISIBLE TEXT of links like `[TEXT](...)`, ignore the target URL.
          - `website` data MUST be a valid http/https URL. Prefer profile pages. EXCLUDE mailto:, tel:.
          - `email` data should ONLY contain email addresses.
        - Term Dates (`start_date`, `end_date`):
          - **Allowed Formats**: Only extract dates that appear in the source text using one of these exact formats: `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`.
          - **Exact Extraction**: Extract the date string *exactly as found*. **DO NOT** add default months or days (like '-01', '-31', '-01-01', '-12-31') if they are not explicitly present in the source date string.
          - **PRIORITY 1: Specific Term Formats**:
            - Check FIRST for patterns starting with "Term:".
            - If `Term: [Date1] to [Date2]` is found (e.g., "Term: January 1, 2023 to December 31, 2026", "Term: Jan 2023 to Dec 2026", "Term: 2023 to 2026"), extract Date1 and Date2. Format the extracted dates precisely as YYYY, YYYY-MM, or YYYY-MM-DD based *only* on the information present in the source text for each date. Extract BOTH dates if the pattern provides them.
            - If `Term: YYYY-YYYY` (e.g., "Term: 2024-2028") is found, extract the first YYYY string into `start_date.data` and the second YYYY string into `end_date.data`.
          - **PRIORITY 2: Keyword Search**: If specific "Term:" formats are not found, THEN look for keywords:
            - `start_date` keywords: 'Term Began:', 'Elected:', 'Sworn In:', 'Appointed:', 'Serving Since:', 'First Elected:', 'Elected in', 'Took Office', 'Started', 'Since:', 'Beginning', 'Commenced', 'Assumed Office:', 'Joined Council', 'Began Service'
            - `end_date` keywords: 'Term Expires:', 'Term Ends:', 'Serving Until:', 'Until:', 'Expires', 'Ending', 'Through', 'Next Election:', 'End of Term:'
            - Extract the date string following these keywords ONLY if it matches one of the allowed formats (YYYY, YYYY-MM, YYYY-MM-DD). Extract it exactly as found.
          - **Null If Not Found/Matched**: If no date is mentioned for a person, or if a mentioned date does not match the allowed formats (YYYY, YYYY-MM, YYYY-MM-DD), set the corresponding field (`start_date` or `end_date`) to null. Do not attempt to parse or reformat dates like "Spring 2024" or "December".
          - **Validation**: After creating the JSON, review each person's `start_date` and `end_date` to ensure the `data` field strictly contains null or a string in YYYY, YYYY-MM, or YYYY-MM-DD format, extracted directly from the source. Ensure no default months/days were added.
        - Association & Uniqueness: Associate details carefully. Ensure only ONE entry per unique person.

        **FINAL MANDATORY CHECK**: Review your entire response for accuracy before submitting.
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
    rescue Faraday::TooManyRequestsError
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
