# frozen_string_literal: true

module Services
  module Prompts
    class GoogleGeminiPrompts
      def self.research_municipality(state, municipality_entry)
        municipality_name = municipality_entry["name"]
        government_types = Core::CityManager.government_types

        %(
        Provide the current elected Mayor and City Council Members for the specified city,
        formatting the response as a JSON object.

        Municipality: #{municipality_name}, #{state}
        Municipality Website (Optional, for context): #{municipality_entry["website"]}

        Instructions:

        1. Figure out the government type of the city. Available government types: #{government_types.join(", ")}

        2. Determine the total number of elected officials on the City Council for #{municipality_name}.
        This total number includes the Mayor (only if available).

        3. Create a JSON object with a single top-level key "people". The value of "people" must be an array.

        4. This array must contain exactly the total number of elected officials determined in step 1.

        5. Within the array, include one entry for the Mayor (or equivalent, only if available)
        and the remaining entries for "Council Member (or equivalent)" roles.

        6 .For each entry in the array, provide the current elected official's name
        only if you are highly certain based on your training data or search results.

        If you are not highly certain of the current name for any specific position,
        or if the information might be outdated or incomplete, set the 'name' field
        to null for that entry.

        Return ONLY the following JSON structure. Ensure the JSON is perfectly valid and
        can be parsed directly.
        Pay close attention to matching brackets `[]` for arrays and braces `{}` for objects.
        {
          "government_type": The government type of the city (string),
          "people": [{
            "name": The official's name (string) or null,
            "roles": The position held (array of strings),
                         which should be either "Mayor" (only if the municipality has a mayor)
                         or "Council Member" (or equivalent e.g. Selectmen, Alderman).
          }],
          "notes": "Notes about the search and the results"
        }

        IMPORTANT: I need ONLY the JSON object as your response,
        with NO additional text, explanation, or markdown formatting.
        Do not include any text before or after the JSON object.
        Your entire response should be a valid JSON object that can be directly parsed.
        Verify all brackets, braces, quotes, and commas are correct.
      )
      end

      def self.municipality_officials(municipality_context, content, people, person_name = "")
        state = municipality_context[:state]
        municipality_name = municipality_context[:municipality_entry]["name"]
        government_type = municipality_context[:government_type]
        municipality_config = Core::CityManager.get_config(government_type)
        roles = municipality_config["roles"].map { |p| p["role"] }
        division_names = Core::CityManager.divisions.keys
        current_date = Date.today.strftime("%Y-%m-%d")
        maybe_target_people = people.map { |person| person&.dig("name") }.compact

        target_text = if person_name.present?
                        person_name
                      elsif maybe_target_people.present? && maybe_target_people.count.positive?
                        %(the main governing body of the target municipality.
                        If the content includes information about the following people, they are
                        very likely to be on the council:
                        #{maybe_target_people.join(", ")}
                        )
                      else
                        %(the main governing body of the target municipality.)
                      end

        %(
        First, determine if the content contains relevant information about #{target_text}.
        If not, return an empty JSON array `[]`.

        Target Municipality: #{municipality_name}, #{state}
        Target Roles: #{roles.join(", ")}
        Target Divisions: #{division_names.join(", ")}

        Return a JSON object with people, each having:
        - name: Full name only (not titles)
        - phone_number: {data, llm_confidence, llm_confidence_reason}
        - email: {data, llm_confidence, llm_confidence_reason}
        - website: {data, llm_confidence, llm_confidence_reason}
        - roles: [{data, llm_confidence, llm_confidence_reason}]
        - divisions: [{data, llm_confidence, llm_confidence_reason}]
        - start_date: {data, llm_confidence, llm_confidence_reason}
        - end_date: {data, llm_confidence, llm_confidence_reason}

        The JSON object should have the following structure:
        {
          "people": [],
          "thought": "Your reasoning or thought process behind the extraction" // Restrict to 1 sentence.
        }

        Guidelines:
        - For "llm_confidence": Use 0-1 scale with reason for your confidence
        - Roles extraction:
            - Extract roles that match the **target roles** provided (e.g., #{roles.join(", ")}).
            - If a role on the page is ambiguous (e.g., "President"), infer the most accurate match from the target roles list based on **context**:
                - Example: If "President" is listed under "Council Members," infer it as "Council President."
                - Example: If "President" appears without clear context, do not infer or extract it.
            - Provide a confidence score (`llm_confidence`) and a brief reason for the inference.
            - Also extract **contextual variations** of the target roles if they are clearly related (e.g., "Water Commissioner" for "Commissioner").
            - Variations must include the target role as part of the title (e.g., "Water Commissioner" includes "Commissioner").
            - Do NOT extract unrelated roles or roles that do not include the target role (e.g., "Director of Water" should not be extracted for "Commissioner").
            - Include only active roles (today is #{current_date}).
            - Examples:
              - If the target roles include "Council President":
                - A person listed as "President" under "Council Members" → Extract as "Council President".
                - A person listed as "President" without clear context → Do not extract or infer.
              - If the target roles include "Commissioner":
                - A person listed as "Water Commissioner" → Extract as "Commissioner" and "Water Commissioner".  - A person listed as "Director of Water" → Do not extract as "Commissioner".
        - Division extraction:
          - Extract divisions if they are explicitly mentioned in the text
            and are relevant to the person's role in regards to the main governing body.
          - Example: "Council Member for District 3" or "At-Large Councilor" should be extracted as
            "District 3" and "At-Large", respectively.
          - A person can have multiple divisions. List them separately.
        - Name extraction: Extract full names ONLY, not titles
          - CORRECT: "Lisa Brown" (not "Mayor Brown" or "Mayor Lisa Brown")
          - Titles belong in positions array, not in names
        - Phone number extraction:
          - CRITICAL: Extract phone numbers even when formatted as Markdown link text,
            like `[(206) 555-1212]()` or `[Call (206) 555-1212](some-page)`.
            Extract the number within the square brackets.
          - List only one phone number per person.
          - If multiple phone numbers are found, choose the most relevant one based on context.
        - Website extraction:
          - Goal: Find the primary, stable profile or biography page for the person.
          - Prioritize person-specific pages over landing pages (e.g., `/council/john-doe` over `/council/`).
          - Consider links associated with names/photos.
          - Prefer deeper paths and "/about", "/bio", "/profile" pages when available.
          - CRITICAL: The value for "website" MUST be a standard web URL.
          - ONLY include URLs starting with "http://" or "https://".
          - EXCLUDE all other types of links like "mailto:", "tel:", "ftp:", etc.
          - Prefer shorter, cleaner URLs over ones with many complex query parameters unless clearly necessary
            for the specific person's profile page.
        - Email extraction:
          - Extract email addresses found directly in the text.
          - Also extract emails formatted as Markdown link *text*,
            like `[email@example.com]()` or `[email@example.com](some-link)`.
            Extract the email address shown in the brackets.
          - Place extracted emails ONLY in the "email" field, NEVER in the "website" field.
        - **Start and End Date Extraction Guidelines**:
          - **Default to Null**:
            - Both `start_date` and `end_date` must be `null` unless an explicit date is found in the text.
            - Do not infer, assume, or calculate dates based on context, patterns, or common practices.
          - **Allowed Formats**:
            - Extract dates only if explicitly written in one of the following formats:
              - `YYYY`, `YYYY-MM`, or `YYYY-MM-DD` (e.g., "2027", "2027-01", "2027-01-15").
              - `Month YYYY` (e.g., "January 2027") → Convert to `YYYY-MM` (e.g., "2027-01").
            - Any other format should be treated as not found, and the output must be `null`.

          - **Identifying the Correct Start Date**:
            - If multiple `start_date` keywords (e.g., "elected", "reelected") are found:
              - Use the date associated with the **most recent election or re-election**.
              - Example: "elected in November 2020 and reelected in November 2024" → `start_date`: `2024-11`.

          - **Locating Dates**:
            - Use the following keywords and patterns to locate explicit dates:
              - **`start_date` keywords**:
                - 'Elected:', 'Elected in', 'Appointed:', 'Term Began:', 'Sworn In:', 'Serving Since:',
                  'First Elected:', 'Took Office', 'Started', 'Since:', 'Beginning', 'Commenced',
                  'Assumed Office:', 'Joined Council', 'Began Service'.
              - **`end_date` keywords**:
                - 'Term Expires:', 'Term Ends:', 'Term ending', 'Serving Until:', 'Until:', 'Expires',
                  'Ending', 'Through', 'Next Election:', 'End of Term:'.
              - **Patterns**:
                - `Term: [Date1] to [Date2]` → Extract both `start_date` and `end_date`.
                - `Term: YYYY-YYYY` → Extract both `start_date` and `end_date`.

            - Ensure the date is **clearly associated with the specific person** being processed:
              - For tables, the date must appear in the same row or entry as the person's name.
              - For text, the date must be explicitly linked to the person (e.g., "John Doe was elected in 2020").

            - **Handling Ambiguities**:
              - If the text uses vague terms like "last year" or "the usual date", set the date to `null`.
              - If the person has resigned, vacated their role, or is deceased, exclude them entirely from the output.

            - **Key Examples**:
              - "Term Expires January 2027" → `end_date`: `{"data": "2027-01"}`
              - "Serving through 2025" → `end_date`: `{"data": "2025"}`
              - "Term: Jan 2023 to Dec 31, 2026" → `start_date`: `{"data": "2023-01"}`, `end_date`: `{"data": "2026-12-31"}`
              - "Elected last year" → `start_date`: `null`
              - "Term began on the usual date" → `start_date`: `null`
              - "elected in Nov 2020, reelected Nov 2024" → `start_date`: `{"data": "2024-11"}`
              - "term ending December 2028" → `end_date`: `{"data": "2028-12"}`
              - "Elected Nov 2024 for term ending Dec 2028. Resigned April 15." → Exclude this person from the output.

            - **Final Check**:
              - Ensure the extracted date is explicitly written in the text and clearly associated with the correct individual.
              - If not, the output must be `null`. No exceptions for inference or misattribution.
        - Today is #{current_date}. Context only, do not use for date calculation.
        - Association: Contact details (phone, email) listed under common headings like 'Contact' or 'Contact Us'
          that appear structurally close (e.g., immediately following section) to a specific person's name or section
          should be associated with that person unless the text clearly indicates
          otherwise (e.g., 'General City Contact').
          **When processing tabular data, ensure all extracted fields for a single person (name, roles, divisions, dates, etc.)
          are sourced from data within that person's specific row or clearly delineated section.
          Do not carry over or associate data from adjacent rows or different individuals.**
        - Ensure only ONE entry exists per unique person's name.
          Merge all extracted details for the same person into a single record

        Here is the content (in markdown):
        #{content}
       )
      end
    end
  end
end
