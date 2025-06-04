module Services
  module Prompts
    class OpenaiPrompts
      def self.municipality_officials(context, content_file, page_url, people_hint = [], person_name = "")
        content = File.read(content_file)
        state = context[:state]
        government_type = context[:government_type]
        government_types_config = Core::CityManager.get_config(government_type)

        roles = government_types_config["roles"].map { |role| role["role"] }
        division_names = Core::CityManager.divisions.keys
        municipality_entry = context[:municipality_entry]

        maybe_target_people = (people_hint || []).map { |person| person&.dig("name") }.compact

        content_type = if person_name.present?
                         "First, determine if the content contains information about the target person: #{person_name}."
                       else
                         %(Your primary task is to identify and extract information for the members of
                         the primary governing body (e.g., Town Council, City Council, Select Board,
                         Board of Aldermen, Commissioners) of the target municipality found within the provided content.
                         Be cautious with other municipal boards (e.g., Planning Board, Zoning Board,
                         Conservation Commission, etc.) -- they are not the primary governing body.

                         As a helpful guide, the following people might be members of the primary governing body
                         based on previous data:
                         [#{maybe_target_people.join(", ")}].
                         Use this list to aid identification, but DO NOT limit your search to only these names.
                         Extract information for EVERY relevant person you find in the content who is part of
                         the primary governing body, regardless of whether they were on the provided list.
                         If the content does not appear to contain any members of the primary governing body,
                         return an empty JSON array `[]`.
                         )
                       end

        system_instructions = <<~INSTRUCTIONS
          You are an expert data extractor focused on accuracy.

          #{content_type} If not, return an empty JSON array `[]`.

          Target Person (if applicable): #{person_name}
          Target Municipality: #{municipality_entry["name"]}, #{state}
          Target roles: #{roles.join(", ")}
          Division examples: #{division_names.join(",")}

          Return a JSON object with a key "people" containing an array.
          Each object represents one person and MUST include ALL fields
          (name, roles, divisions, image, phone_number, email, website, start_date, end_date),
          populating with extracted data or null.

          Output Field Definitions & Structure:
          - name: (String) Full name only (no titles).
          - roles: (Array of Objects) Active municipal roles.
                   Identify their official job title or specific position.
                   This can be a wide variety of municipal roles (e.g., "Mayor", "City Manager", "Selectman",
                   "Alderman", "Council Member At-Large", "Board Member, Position 2", "Council Member, Seat 5").
                   Focus on capturing the most complete and meaningful description of
                   their individual position as it appears in the text, regardless of the specific title.
                    [{data: "Mayor", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}]
          - divisions: (Array of Objects) Specific division/district/ward and name/number,
                    only if specified (e.g., "Ward 1", "District 2", "Position 3", "Seat Blue").
                    [{data: "Ward 1", llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}].
          - image: (Object or null) {data: "https://www.seattle.gov/images/MayorHarrell/mayor-bruce-harrell.jpg",#{" "}
                                    llm_confidence: 0.0-1.0, llm_confidence_reason: "..."}
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
                "roles": [{data: "Mayor", "llm_confidence": 0.95, "llm_confidence_reason": "Found 'Mayor' in the text."}],
                "divisions": [],
                "image": {"data": "https://www.orcity.org/headshot.jpg", "llm_confidence": 0.95,
                          "llm_confidence_reason": "Found image labeled 'Mayor Denyse McGriff' near name."},
                "phone_number": {"data": "503-656-3912", "llm_confidence": 0.95, "llm_confidence_reason": "Found number labeled 'Home:' near name."},
                "email": {"data": "dmcgriff@orcity.org", "llm_confidence": 0.98, "llm_confidence_reason": "Extracted from mailto link text near name."},
                "website": {"data": "https://www.orcity.org/1772/Mayor-Denyse-McGriff", "llm_confidence": 0.9, "llm_confidence_reason": "Primary page URL."},
                "start_date": {"data": "2023-01-01", "llm_confidence": 0.99,"llm_confidence_reason": "Extracted start date from 'Term: January 1, 2023 to ...'"},
                "end_date": {"data": "2026-12-31", "llm_confidence": 0.99, "llm_confidence_reason": "Extracted end date from 'Term: ... to December 31, 2026'"}
              }, {
                "name": "Adam Marl",
                "roles": [{data: "Council Member", "llm_confidence": 0.95, "llm_confidence_reason": "Found 'Council Member' in the text."}],
                "divisions": ["Ward 1"],
                "image": {"data": "https://www.orcity.org/images/f7ac574487389ed707b5d516d17500f55ca16e63d4b8100ef310b0d792cce875.jpg",
                          "llm_confidence": 0.95, "llm_confidence_reason": "Found image labeled 'Commissioner Adam Marl' near name."},
                "phone_number": {"data": "503-406-8165", "llm_confidence": 0.95, "llm_confidence_reason": "Found number labeled 'Cell:' near name."},
                "email": {"data": "amarl@orcity.org", "llm_confidence": 0.98, "llm_confidence_reason": "Extracted from mailto link text near name."},
                "website": {"data": "https://www.orcity.org/1775/Commissioner-Adam-Marl", "llm_confidence": 0.9, "llm_confidence_reason": "Primary page URL."},
                "start_date": {"data": "2023-01-01", "llm_confidence": 0.99,"llm_confidence_reason": "Extracted start date from 'Term: January 1, 2023 to ...'"},
                "end_date": {"data": "2026-12-31", "llm_confidence": 0.99, "llm_confidence_reason": "Extracted end date from 'Term: ... to December 31, 2026'"}
              }, {
                "name": "Example Person",
                "roles": ["Council Member At-Large"],
                "divisions": [],
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
          - General: Merge details for the same person. Assign confidence (0-1 scale) + brief reason for each field\'s data.
          - Name: Extract full names ONLY (e.g., "Denyse McGriff", not "Mayor Denyse McGriff"). Titles go in \'positions\'.
          - Roles:
            - Extract ONLY active roles matching Target Roles/Examples (municipal legislative/executive).
            - **Focus on Main Governing Body**: Prioritize extracting members of the primary municipal governing body
              (e.g., Town Council, City Council, Select Board). The `Key roles` and `Examples` provided to you#{" "}
              primarily refer to positions on this main body.
            - **Handling Resignations/Vacancies**: If the text explicitly states that a person has **resigned, vacated their position, is deceased,
              or their position is otherwise noted as vacant (e.g., "applications being accepted for this seat")**,
              DO NOT include them as a current office holder or extract their position.
              The statement of resignation or vacancy takes precedence over any listed future term dates when determining current active status.
              For example, if a person was "Elected Nov 2024 for term ending Dec 2028" but then "Resigned April 15",#{" "}
              they should NOT be included in the output as an active member.
          - Image: Extract URL of portrait/headshot near name. Ignore logos, banners, icons. Check alt text but prioritize proximity/style.
          - Contact Details (Phone/Email/Website):
            - Associate details logically if near the person's name/section.
            - Phone Prefixes: Extract number after labels like "Office:", "Cell:", "Mobile:", "Direct:", "Home:". Exclude "Fax:". Format numbers simply.
            - Markdown Links: Extract email/phone from the VISIBLE TEXT of links like `[TEXT](...)`, ignore the target URL.
            - `website` data MUST be a valid http/https URL. Prefer profile pages. EXCLUDE mailto:, tel:.
            - `email` data should ONLY contain email addresses.
          - Term Dates (`start_date`, `end_date`):
            - Extract start_date and end_date in YYYY, YYYY-MM, or YYYY-MM-DD format.
            - Acceptable date phrases include:
              - “Elected [date]”, “Appointed [date]”, “Term: [date1] to [date2]”, “Since [date]”.
              - Convert natural language to proper format (e.g., "January 2025" → 2025-01)
              - For vague phrases like "Spring 2025", extract the year only.

          **FINAL MANDATORY CHECK**: Review your entire response for accuracy before submitting,#{" "}
            paying close attention to the date extraction, conversion, and term identification rules.
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
    end
  end
end
