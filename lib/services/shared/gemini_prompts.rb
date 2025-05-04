# frozen_string_literal: true

module Services
  module Shared
    class GeminiPrompts
      def self.gemini_generate_search_for_people_prompt(state, municipality_entry)
        city_name = municipality_entry["name"]

        %(
        Provide the current elected Mayor and City Council Members for the specified city,
        formatting the response as a JSON object.

        City: #{city_name}, #{state}
        City Website (Optional, for context): #{municipality_entry["website"]}

        Instructions:

        First, determine the total number of elected officials on the City Council for #{city_name}.
        This total number includes the Mayor.

        Create a JSON object with a single top-level key "people". The value of "people" must be an array.

        This array must contain exactly the total number of elected officials determined in step 1.

        Within the array, include one entry for the Mayor and the remaining entries for "Council Member" positions.

        For each entry in the array, provide the current elected official's name
        only if you are highly certain based on your training data or search results.

        If you are not highly certain of the current name for any specific position,
        or if the information might be outdated or incomplete, set the 'name' field to null for that entry.

        Each object in the array must have two keys:
        {
          "name": The official's name (string) or null.
          "positions": The position held (array of strings), which should be either "Mayor" or "Council Member" (or equivalent).
        })
      end

      def self.gemini_generate_municipal_directory_prompt(municipality_context, content, person_name = "")
        state = municipality_context[:state]
        municipality_name = municipality_context[:municipality_entry]["name"]
        government_type = municipality_context[:government_type]
        positions = Core::CityManager.get_position_roles(government_type)
        divisions = Core::CityManager.get_position_divisions(government_type)
        position_examples = Core::CityManager.get_position_examples(government_type)
        current_date = Date.today.strftime("%Y-%m-%d")
        maybe_target_people = municipality_context[:config]["source_directory_list"]["people"].compact.map do |person|
          person&.dig("name")
        end

        target_text = if person_name.present?
                        person_name
                      else
                        %(the council members (including the mayor) of the target municipality.
                        If the content includes information about the following people, they are
                        very likely to be on the council:
                        #{maybe_target_people.join(", ")}
                        )
                      end

        %(
        You are an expert data extractor.

        First, determine if the content contains relevant information about #{target_text}.
        If not, return an empty JSON array `[]`.

        Target Municipality: #{municipality_name}, #{state}
        Target Municipal Roles: #{positions.join(", ")} (Examples: #{position_examples})
        Associated Divisions: #{divisions.join(", ")}

        Return a JSON object with people, each having:
        - name: Full name only (not titles)
        - phone_number: {data, llm_confidence, llm_confidence_reason, }
        - email: {data, llm_confidence, llm_confidence_reason, }
        - website: {data, llm_confidence, llm_confidence_reason, }
        - positions: [array of strings]
        - start_date: {data, llm_confidence, llm_confidence_reason, }
        - end_date: {data, llm_confidence, llm_confidence_reason, }

        Format example:
        {
          "people": [
            {
              "name": "John Doe",
              "phone_number": {"data": "123-456-7890", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under Contact."},
              "email": {"data": "john.doe@example.com", "llm_confidence": 0.95, "llm_confidence_reason": "Directly associated with name."},
              "website": {"data": "https://example.com/john-doe", "llm_confidence": 0.95, "llm_confidence_reason": "Found under header"},
              "positions": ["Mayor", "Council Member"],
              "start_date": {"data": "2022-01-01", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under header."},
              "end_date": {"data": "2022-12-31", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under header."}
            },
            {
              "name": "Jane Smith",
              "phone_number": {"data": "(987) 654-3210", "llm_confidence": 0.90, "llm_confidence_reason": "Extracted from markdown link text like [(987) 654-3210]()"},
              "email": {"data": "jane.smith@example.gov", "llm_confidence": 0.92, "llm_confidence_reason": "Found under 'Contact Us' section near name."},
              "positions": ["Council President"],
              "end_date": {"data": "2027-12-31", "llm_confidence": 0.95, "llm_confidence_reason": "Found phrase 'Term Expires December 31, 2027'"}
            }
          ]
        }

        Guidelines:
        - For "llm_confidence": Use 0-1 scale with reason for your confidence
        - For positions:
          - **CRITICAL**: Extract ONLY roles matching or functionally equivalent to the
            **Target Municipal Roles** and **Examples** provided
          - Include only active roles (today is #{current_date}).
          - Include both the role and any associated division (e.g., "Council Member, District 3").
        - Name extraction: Extract full names ONLY, not titles
          - CORRECT: "Lisa Brown" (not "Mayor Brown" or "Mayor Lisa Brown")
          - Titles belong in positions array, not in names
        - Phone number extraction:
          - CRITICAL: Extract phone numbers even when formatted as Markdown link text,
            like `[(206) 555-1212]()` or `[Call (206) 555-1212](some-page)`.
            Extract the number within the square brackets.
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
        - start_date and end_date extraction:
          - Format: YYYY, YYYY-MM-DD or null
          - SEARCH FOR END DATES using these patterns:
            - "Term Expires:"
            - "Term Ends:"
            - "Serving Until:"
            - "Until:"
            - "Next Election:"
            - "End of Term:"
            - "Through"
            - "Expires"
            - "Ending"
          - Date format rules:
            - Years only: use YYYY format (e.g., "2025")
            - Month and year: use YYYY-MM-01 format
            - Complete dates: use YYYY-MM-DD format
          - EXAMPLES - end dates (CRITICAL TO EXTRACT):
            - "Term expires December 31, 2026" → end_date: {"data": "2026-12-31"}
            - "Term expires December 2026" → end_date: {"data": "2026-12-01"}
            - "Serving through 2025" → end_date: {"data": "2025"}
            - "Next election: November 2024" → end_date: {"data": "2024-11-01"}
        - Today is #{current_date}. Ensure that only active positions are included, and
          exclude any positions that are not currently held or are no longer active.
        - Association: Contact details (phone, email) listed under common headings like 'Contact' or 'Contact Us'
          that appear structurally close (e.g., immediately following section) to a specific person's name or section
          should be associated with that person unless the text clearly indicates otherwise (e.g., 'General City Contact').
        - Ensure only ONE entry exists per unique person's name.
          Merge all extracted details for the same person into a single record

        **MANDATORY DATE CHECK**: Before finalizing, verify: If the text clearly stated a term start or end
        date/year(s) for a person (like "Term Expires 2025" or "Term: 2023-2026"),
        did you populate `start_date` and/or `end_date`?
        Do not leave these fields null if the information was present.

        Here is the content:
        #{content}
       )
      end
    end
  end
end
