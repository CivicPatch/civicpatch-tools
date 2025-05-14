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
  MAX_TOKENS = 100_000

  class Openai
    MODEL = "gpt-4.1-mini"

    def initialize
      @client = OpenAI::Client.new(access_token: ENV["OPENAI_TOKEN"])
    end

    def extract_city_people(municipality_context, content_file, page_url, person_name = "")
      state = municipality_context[:state]
      municipality_entry = municipality_context[:municipality_entry]

      content = File.read(content_file)

      return { error: "Content for city council members are too long" } if content.split(" ").length > MAX_TOKENS

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

    def generate_city_info_prompt(municipality_context, content, page_url, person_name = "") # rubocop:disable Metrics/AbcSize,Metrics/MethodLength
      state = municipality_context[:state]
      government_type = municipality_context[:government_type]
      government_types_config = Core::CityManager.get_config(government_type)
      positions = government_types_config["positions"].map { |position| position["role"] }
      divisions = government_types_config["positions"].flat_map { |position| position["divisions"] }
      position_examples = government_types_config["position_examples"]
      municipality_entry = municipality_context[:municipality_entry]
      current_date = Date.today.strftime("%Y-%m-%d")

      maybe_target_people = municipality_context[:config]["source_directory_list"]["people"].compact.map do |person|
        person&.dig("name")
      end

      content_type = if person_name.present?
                       "First, determine if the content contains information about the target person."
                     else
                       %(Your primary task is to identify and extract information for ALL members of
                         the primary governing body (e.g., Town Council, City Council, Select Board,
                         Board of Aldermen, Commissioners)
                         of the target municipality found within the provided content.
                         Be cautious with other municipal boards (e.g., Planning Board, Zoning Board,
                         Conservation Commission, etc.).
                         Only extract individuals from these secondary boards if their listed role explicitly
                         indicates they are also a representative FROM or TO the primary governing body
                         (e.g., "Town Council Representative to the Planning Board", "Select Board Liaison").
                         If their role on a secondary board does not clearly state a connection to
                         the primary governing body, they should typically be excluded unless the content
                         strongly suggests they are also primary governing body members.

                         As a helpful guide, the following people might be members of the primary governing body
                         based on previous data:
                         [#{maybe_target_people.join(", ")}].
                         Use this list to aid identification, but DO NOT limit your search to only these names.
                         Extract information for EVERY relevant person you find in the content who is part of
                         the primary governing body, regardless of whether they were on the provided list.
                         If the content does not appear to contain members of the primary governing body,
                         return an empty JSON array `[]`.
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
        - image: (String or null) URL of the person's portrait/headshot (usually starts 'images/'). **IMPORTANT: This field must be a simple string (the URL) or null. It should NOT be an object and should NOT include confidence scores.**
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
        - General: Today is #{current_date}. Merge details for the same person. Assign confidence (0-1 scale) + brief reason for each field\'s data.
        - Name: Extract full names ONLY (e.g., "Denyse McGriff", not "Mayor Denyse McGriff"). Titles go in \'positions\'.
        - Positions:
          - Extract ONLY active roles matching Target Roles/Examples (municipal legislative/executive).
          - **Focus on Main Governing Body**: Prioritize extracting members of the primary municipal governing body (e.g., Town Council, City Council, Select Board). The `Key roles` and `Examples` provided to you primarily refer to positions on this main body.
          - **Secondary Boards (e.g., Planning Board, Zoning Board, Commissions):**
            - If the content is clearly about a specific secondary board (e.g., a page titled "Planning Board Members" or "Zoning Commission Roster"):
              - **Do NOT extract individuals solely based on leadership roles held *within that specific secondary board* (such as \'Chair of the Planning Board\', \'Planning Board Vice-Chair\', \'Zoning Secretary\').** These titles by themselves do not make them members of the primary governing body.
              - ONLY extract an individual from such a page if their listed role *also explicitly and unambiguously* indicates they are concurrently a member of, or a designated representative/liaison FROM or TO, the primary governing body (e.g., "Town Council Representative to the Planning Board", "Selectman Liaison to Conservation", "Council Member (also on Zoning Board)").
              - *Example*: If a page lists "Jane Doe, Chair" under "Planning Board Members", and no other role links Jane Doe to the Town Council, Jane Doe should NOT be extracted as a member of the primary governing body. However, if the page lists "John Smith, Town Council Rep.", John Smith SHOULD be extracted with his primary role as "Town Council Member" (if that is a key role) and optionally "Town Council Rep." if that detail is desired.
            - If a person *is* identified as a representative from the primary governing body *to* a secondary board (as in the John Smith example above), ensure you extract their role on the primary governing body (e.g., "Council Member" if that is a Key Role from your list of target roles).
          - **Handling Resignations/Vacancies**: If the text explicitly states that a person has **resigned, vacated their position, is deceased, or their position is otherwise noted as vacant (e.g., "applications being accepted for this seat")**, DO NOT include them as a current office holder or extract their position. The statement of resignation or vacancy takes precedence over any listed future term dates when determining current active status. For example, if a person was "Elected Nov 2024 for term ending Dec 2028" but then "Resigned April 15", they should NOT be included in the output as an active member.
          - **Include specific division, district, or position identifier if present.**
            - If the source uses numeric identifiers like "#1", "No. 2", or similar for a role (e.g., in a table column named "Position" or "District"), interpret this as a position number.
            - **Prefer the term "Position X" (e.g., "Position 1", "Position 2") when a numeric identifier is used, unless the source text clearly and consistently uses a different term like "Seat X" or "Ward X" for those numbered roles on the same page.**
            - Combine with the main role, e.g., "Council Member, Position 1".
          - EXCLUDE judicial, most admin staff, non-municipal.
          - For position extraction:
            - **Core Membership Role Inclusion**:
              - The `Key roles` list provided to you contains canonical names for primary/core membership roles on the main governing body (e.g., "Council Member", "Select Board Member", "Commissioner", "Alderman", "Trustee").
              - For each person, if their roles extracted directly from the text include:
                  a) A *leadership position* from the `Key roles` list that applies to the main governing body (e.g., "Mayor" if they preside over the Council, "Chair", "President"), OR
                  b) Any other role from the `Key roles` or `Examples` that clearly signifies membership on that main governing body (even if it\'s a more specific version, a common variation, or an alias of a core membership role – e.g., text says "Selectman" and "Select Board Member" is a Key Role; text says "Councilmember At-Large" and "Council Member" is a Key Role),
              - THEN you MUST ensure that the relevant canonical primary/core membership role from `Key roles` (e.g., "Select Board Member", "Council Member") is included in their `positions` array.
              - *Example*: If "Council Member" is a key core role, a person listed as "Council President" should have both "Council President" AND "Council Member" in their positions. If "Select Board Member" is a key core role, a person listed only as "Selectman" (a common variation/alias) should also have "Select Board Member" listed.
            - **Additional Specific Roles**:
              - In addition to the ensured core membership role, also include all other distinct, active municipal roles or more specific titles found in the text, provided they match the `Key Roles` or `Examples` OR if they represent a clear representative role from the primary governing body to another board/commission. This includes specific committee assignments, liaison roles, or detailed versions of their main role if they add clarity beyond the core membership role (e.g., "Council Member, Ward 3", "Select Board Representative to Finance Committee").
            - **Clarity and Conciseness**:
              - When multiple terms in the text describe the exact same specific responsibility (e.g., "Board of Selectmen\'s Representative to Planning Board" and "Selectmen\'s Rep to Planning Board"), prefer the most complete, official-sounding, or consistently used term from the source for that specific responsibility. Avoid redundant listings *for the exact same specific role* if one is merely an abbreviation of the other. However, this does not override the rule to include both the core membership role and a more specific title if they represent different levels of detail (e.g., "Council Member" and "Council Member, District A").
        - Image: Extract URL of portrait/headshot near name. Ignore logos, banners, icons. Check alt text but prioritize proximity/style. URL should usually start \'images/\'. **The output for the 'image' field in the JSON must be the direct URL string or null; do NOT wrap it in an object with 'data' or 'llm_confidence'.**
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
          - **Identifying the Correct Term's Start Date**:
            - When multiple dates or events (e.g., appointment, election, term beginning) are mentioned for the start of a council member's service:
              - **PRIORITY 1 for Start Date**: If an **"elected" date** (e.g., "elected in November 2024", "elected [Month YYYY]") is explicitly stated for the current or upcoming term, that "elected" date should be used as the `start_date`.
              - **PRIORITY 2 for Start Date**: If no "elected" date is available for the current/upcoming term, but an "appointed" date is, use the "appointed" date.
              - **PRIORITY 3 for Start Date**: If neither "elected" nor "appointed" dates are specified for the current/upcoming term, use the date when the term officially "began" or "started" (e.g., "term beginning January 2025").
            - Ensure the chosen `start_date` corresponds to the **most recent term that is currently active or the next term set to begin as of #{current_date}**, following the priority above.
            - This also means if a resignation has occurred, the term is no longer considered active or upcoming for that individual.
            - Example: If text says "appointed June 2023, elected November 2023 for term starting January 2024", the `start_date` should be based on "elected November 2023" (converted to YYYY-MM).
          - **PRIORITY 1: Specific Term Formats**:
            - Check FIRST for patterns starting with "Term:".
            - If `Term: [Date1] to [Date2]` is found, extract Date1 and Date2. Apply the Input Recognition & Conversion rules above to each date individually based on how it appears in the source. Extract BOTH dates if the pattern provides them.
            - If `Term: YYYY-YYYY` (e.g., "Term: 2024-2028") is found, extract the first YYYY string into `start_date.data` and the second YYYY string into `end_date.data`.
          - **PRIORITY 2: Keyword Search**: If specific "Term:" formats are not found, THEN look for keywords:
            - `start_date` keywords: 'Term Began:', 'Elected:', 'Sworn In:', 'Appointed:', 'Serving Since:', 'First Elected:', 'Elected in', 'Took Office', 'Started', 'Since:', 'Beginning', 'Commenced', 'Assumed Office:', 'Joined Council', 'Began Service'
            - `end_date` keywords: 'Term Expires:', 'Term Ends:', 'Serving Until:', 'Until:', 'Expires', 'Ending', 'Through', 'Next Election:', 'End of Term:'
            - Extract the date string following these keywords. Apply Input Recognition & Conversion rules. When multiple `start_date` keywords match, use the "Identifying the Correct Term's Start Date" logic above to choose.
          - **Null If Not Found/Matched/Convertible**: If no date is mentioned, or if a mentioned date cannot be reliably recognized and converted into one of the allowed output formats (YYYY, YYYY-MM, YYYY-MM-DD), set the corresponding field (`start_date` or `end_date`) to null. Do not attempt to parse ambiguous text like "Spring 2024".
          - **Validation**: After creating the JSON, review each person's `start_date` and `end_date`.
            - Ensure the `data` field strictly contains null or a string matching YYYY, YYYY-MM, or YYYY-MM-DD, reflecting defined conversion rules.
            - Verify that if multiple start events (elected, appointed, term began) were mentioned, the `start_date` reflects the "elected" date if available for the current/upcoming term, otherwise following the specified priority.
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
      rescue JSON::ParserError => e
        puts "JSON Parsing Error for #{municipality_name}, #{state}: #{e.message}"
        puts "Problematic JSON string was:\n#{json_output}"
        nil
      rescue StandardError => e
        puts "Other StandardError during JSON processing for #{municipality_name}, #{state}: #{e.message}"
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
