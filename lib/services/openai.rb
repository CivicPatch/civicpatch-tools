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
      response = run_prompt(messages, state, municipality_entry["name"])

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
        - positions: (Array of Strings) Active municipal roles. Include specific division/district/position number (e.g., "Council Member, Position 1").
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
            }, {
              "name": "Example Person",
              "positions": ["Council Member"],
              "image": null,
              "phone_number": null,
              "email": null,
              "website": null,
              "start_date": null,
              "end_date": {"data": "2026-12", "llm_confidence": 0.97, "llm_confidence_reason": "Extracted from 'Term Expires December 2026'"}
            }
          ]
        }

        Extraction Guidelines:
        - General: Today is #{current_date}. Merge details for the same person. Assign confidence (0-1 scale) + brief reason for each field's data.
        - Name: Extract full names ONLY (e.g., "Denyse McGriff", not "Mayor Denyse McGriff"). Titles go in 'positions'.
        - Positions:
          - Extract ONLY active roles matching Target Roles/Examples (municipal legislative/executive).
          - **Include specific division, district, or position identifier if present.**
            - If the source uses numeric identifiers like "#1", "No. 2", or similar for a role (e.g., in a table column named "Position" or "District"), interpret this as a position number.
            - **Prefer the term "Position X" (e.g., "Position 1", "Position 2") when a numeric identifier is used, unless the source text clearly and consistently uses a different term like "Seat X" or "Ward X" for those numbered roles on the same page.**
            - Combine with the main role, e.g., "Council Member, Position 1".
          - EXCLUDE judicial, most admin staff, non-municipal.
        - Image: Extract URL of portrait/headshot near name. Ignore logos, banners, icons. Check alt text but prioritize proximity/style. URL should usually start 'images/'.
        - Contact Details (Phone/Email/Website):
          - Associate details logically if near the person's name/section.
          - Phone Prefixes: Extract number after labels like "Office:", "Cell:", "Mobile:", "Direct:", "Home:". Exclude "Fax:". Format numbers simply.
          - Markdown Links: Extract email/phone from the VISIBLE TEXT of links like `[TEXT](...)`, ignore the target URL.
          - `website` data MUST be a valid http/https URL. Prefer profile pages. EXCLUDE mailto:, tel:.
          - `email` data should ONLY contain email addresses.
        - Term Dates (`start_date`, `end_date`):
          - **Allowed Output Formats**: The final `data` field MUST contain null or a string matching exactly `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`.
          - **Input Recognition & Conversion**:
            - Recognize dates in the source text that appear as `YYYY`, `YYYY-MM`, `YYYY-MM-DD`, or common textual formats like `Month YYYY` (e.g., "December 2026", "Jan 2025"), `Month Day, YYYY` (e.g., "January 31, 2025"), or `MM/DD/YYYY` (e.g., "01/31/2025").
            - If the source date already matches an allowed output format (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`), extract it *exactly as found*.
            - If the source date matches a `Month YYYY` format, convert it to `YYYY-MM` (e.g., "December 2026" becomes "2026-12").
            - If the source date matches `Month Day, YYYY` (e.g., "January 31, 2025"), convert it to `YYYY-MM-DD` (e.g., "2025-01-31").
            - If the source date matches `MM/DD/YYYY` (e.g., "01/31/2025"), convert it to `YYYY-MM-DD` (e.g., "2025-01-31").
            - Use numerical months (01-12) for conversions.
            - **DO NOT** add default days (like '-01', '-31') if they are not explicitly present in the source and required by the `YYYY-MM-DD` format. Do not add default months if only `YYYY` is present.
          - **Identifying the Correct Term**:
            - If multiple terms or election dates are mentioned for a person (e.g., initial election and subsequent re-elections), prioritize extracting the `start_date` for the **most recent term that is currently active or the next term set to begin as of #{current_date}**.
            - Look for phrases like "re-elected to term beginning...", "current term started...", "next term begins..." to identify the relevant active/upcoming term.
            - If a person was "elected in YYYY1, re-elected in YYYY2, and re-elected again in YYYY3", and YYYY3 is the latest and applies to the current/next term, YYYY3 (and its corresponding month/day if available and convertible) should be the basis for the `start_date`.
          - **PRIORITY 1: Specific Term Formats**:
            - Check FIRST for patterns starting with "Term:".
            - If `Term: [Date1] to [Date2]` is found, extract Date1 and Date2. Apply the Input Recognition & Conversion rules above to each date individually based on how it appears in the source. Extract BOTH dates if the pattern provides them.
            - If `Term: YYYY-YYYY` (e.g., "Term: 2024-2028") is found, extract the first YYYY string into `start_date.data` and the second YYYY string into `end_date.data`.
          - **PRIORITY 2: Keyword Search**: If specific "Term:" formats are not found, THEN look for keywords:
            - `start_date` keywords: 'Term Began:', 'Elected:', 'Sworn In:', 'Appointed:', 'Serving Since:', 'First Elected:', 'Elected in', 'Took Office', 'Started', 'Since:', 'Beginning', 'Commenced', 'Assumed Office:', 'Joined Council', 'Began Service'
            - `end_date` keywords: 'Term Expires:', 'Term Ends:', 'Serving Until:', 'Until:', 'Expires', 'Ending', 'Through', 'Next Election:', 'End of Term:'
            - Extract the date string following these keywords. Apply the Input Recognition & Conversion rules (and Correct Term identification) above to the extracted string. Output only if the result matches an allowed output format.
          - **Null If Not Found/Matched/Convertible**: If no date is mentioned, or if a mentioned date cannot be reliably recognized and converted into one of the allowed output formats (YYYY, YYYY-MM, YYYY-MM-DD), set the corresponding field (`start_date` or `end_date`) to null. Do not attempt to parse ambiguous text like "Spring 2024".
          - **Validation**: After creating the JSON, review each person's `start_date` and `end_date`.
            - Ensure the `data` field strictly contains null or a string matching YYYY, YYYY-MM, or YYYY-MM-DD, reflecting defined conversion rules.
            - **Verify that if multiple term start dates were mentioned, the extracted `start_date` corresponds to the most recent active or upcoming term.**
        - Association & Uniqueness: Associate details carefully. Ensure only ONE entry per unique person.

        **FINAL MANDATORY CHECK**: Review your entire response for accuracy before submitting, paying close attention to the date extraction, conversion, and term identification rules.
      INSTRUCTIONS

      content = <<~CONTENT
        #{content}
      CONTENT

      user_instructions = <<~USER
        The page URL is: #{page_url}
        Here is the content (in markdown):
        #{content}
      USER

      [system_instructions, user_instructions]
    end

    private

    def run_prompt(messages, state, municipality_name)
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
      Utils::CostsHelper.log_llm_cost(state, municipality_name, "openai", input_tokens_num, output_tokens_num, MODEL)

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
