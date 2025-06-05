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
        Target Roles: #{roles.join(", ")}
        Target Divisions: #{division_names.join(", ")}

        Return a JSON object with people, each having:
        - name: Full name only (not titles)
        - phone_number: {data, llm_confidence, llm_confidence_reason, }
        - email: {data, llm_confidence, llm_confidence_reason}
        - website: {data, llm_confidence, llm_confidence_reason}
        - roles: [{data, llm_confidence, llm_confidence_reason}]
        - divisions: [{data, llm_confidence, llm_confidence_reason}]
        - start_date: {data, llm_confidence, llm_confidence_reason}
        - end_date: {data, llm_confidence, llm_confidence_reason}

        Format example:
        {
          "people": [
            {
              "name": "John Doe",
              "phone_number": {"data": "123-456-7890", "llm_confidence": 0.95,
                               "llm_confidence_reason": "Listed under Contact."},
              "email": {"data": "john.doe@example.com", "llm_confidence": 0.95,
                               "llm_confidence_reason": "Directly associated with name."},
              "website": {"data": "https://example.com/john-doe", "llm_confidence": 0.95,
                                "llm_confidence_reason": "Found under header"},
              "roles": [{"data": "Council Member", "llm_confidence": 0.95,
                                "llm_confidence_reason": "Listed under header."},
                        {"data": "Mayor", "llm_confidence": 0.90,
                                "llm_confidence_reason": "Listed under header."}],
              "divisions": [{"data": "District 1", "llm_confidence": 0.90
                                "llm_confidence_reason": "Listed under header."}],
              "start_date": {"data": "2022-01-01", "llm_confidence": 0.95,
                                "llm_confidence_reason": "Listed under header."},
              "end_date": {"data": "2022-12-31", "llm_confidence": 0.95,
                                "llm_confidence_reason": "Listed under header."}
            },
            {
              "name": "Jane Smith",
              "phone_number": {"data": "(987) 654-3210", "llm_confidence": 0.90,
                              "llm_confidence_reason": "Extracted from markdown link text like [(987) 654-3210]()"},
              "email": {"data": "jane.smith@example.gov", "llm_confidence": 0.92,
                              "llm_confidence_reason": "Found under 'Contact Us' section near name."},
              "roles": [{"data": "Council President", "llm_confidence": 0.95,
                                "llm_confidence_reason": "Found under header."}],
              "divisions": [{"data": "At-Large", "llm_confidence": 0.90,
                                "llm_confidence_reason": "Found under header."}],
              "end_date": {"data": "2027-12-31", "llm_confidence": 0.95,
                              "llm_confidence_reason": "Found phrase 'Term Expires December 31, 2027'"}
            }
          ]
        }

        Guidelines:
        - For "llm_confidence": Use 0-1 scale with reason for your confidence
        - Roles extraction:
          - **CRITICAL**: Extract roles that EXACTLY MATCH or are CLEAR SYNONYMS for the
            **Target Municipal Roles** and **Examples** provided, AND are **currently active** as of #{current_date}.
          - **Handling Resignations/Vacancies**: If the text explicitly states that a person has **resigned,
            vacated their role, is deceased, or their roleis otherwise noted as vacant
            (e.g., "applications being accepted")**, DO NOT include them as a current office holder or extract their
            role, even if a future term date is also mentioned. The statement of resignation or vacancy takes
            precedence over listed term dates for determining current active status.
          - **Check for Past Dates**: Before extracting a specific role title (e.g., "Council President", "Chair"),
            examine the surrounding text for associated dates or date ranges (e.g., "served as ... from 2011-2012",
            "President in 2015", "(2011-2012)"). If such dates clearly indicate the role was held **only in the past**
            and is not the person's current role, **DO NOT extract that specific role title.** Focus only on roles
            the person currently holds according to the text.
          - **EXCLUDE**: Do NOT extract roles that are clearly advisory, honorary, student/youth positions
            (e.g., "Youth Councilor", "Student Representative"),
            or non-voting unless they are explicitly listed in the Target Municipal Roles.
            Focus on the primary elected/appointed governing body members.
          - Include only active roles (today is #{current_date}).
        - Division extraction:
          - Extract divisions, districts, or wards ONLY if they are explicitly mentioned in the text
            and are relevant to the person's current role.
            Example: "Council Member for District 3" or "At-Large Councilor" should be extracted as
            "District 3" and "At-Large", respectively.
          - A person can have multiple divisions. List them separately.
            - Examples:
              - "Citywide Position 7" -> "Citywide", "Position 7"
              - "At-Large 1, Seat 2" -> "At-Large 1", "Seat 2"
              - "At-Large B" -> "At-Large B" ->
          - Loose associations (the person lives in a district, but not elected from it)
            should not be listed
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
        - start_date and end_date extraction:
          - **Default to Null**: The `data` field for `start_date` and `end_date` MUST be null by default.
            Only populate it if you find an EXPLICIT date string in the text that meets the criteria below.
          - **Prohibited Actions**:
            - **DO NOT infer, assume, or calculate dates** based on context, patterns, "common practice",
              "typical term start", "recently", the current date (`#{current_date}`), or any other non-explicit
              information. **Confidence reasoning like "Common term start date..." is specifically forbidden
              if the date wasn't explicitly written.** Output MUST be null in such cases.
            - Do not add default days or months unless performing the specific `Month YYYY` -> `YYYY-MM` conversion.
          - **Allowed Extraction & Formatting (Only if explicit date found)**:
            - Allowed output formats: `YYYY`, `YYYY-MM`, `YYYY-MM-DD`.
            - If the source text explicitly provides a date as `YYYY`, `YYYY-MM`,
              or `YYYY-MM-DD`, output that exact string.
            - If the source text explicitly provides a date as `Month YYYY` (e.g., "January 2027"),
              convert it to `YYYY-MM` (e.g., "2027-01").
            - If the source text provides an explicit date in any other format, treat it as not found and output null.
          - **Identifying the Correct Start Date (if multiple 'elected' dates)**:
            - If multiple "elected" or "reelected" dates are mentioned for a person, use the date associated with the
              **most recent** election/re-election for the `start_date`.
            - Example: "elected in November 2020 and was reelected in November 2024" → `start_date` should
              be based on "November 2024".
          - **Locating Dates**:
            - Use keywords (`start_date` keywords: 'Elected:', 'Elected in', 'Appointed:', 'Term Began:', 'Sworn In:',
            'Serving Since:', 'First Elected:', 'Took Office', 'Started', 'Since:', 'Beginning', 'Commenced',
            'Assumed Office:', 'Joined Council', 'Began Service', `end_date` keywords: 'Term Expires:', 'Term Ends:',
            'Term ending', 'Serving Until:', 'Until:', 'Expires', 'Ending', 'Through', 'Next Election:', 'End of Term:')
             and patterns (`Term: [Date1] to [Date2]`, `Term: YYYY-YYYY`) to find potential explicit date strings
             **that are clearly associated with the specific person being processed.**
            - When multiple `start_date` keywords like "elected" or "reelected" are found,
              apply the "Identifying the Correct Start Date" rule above.
            - When extracting from tables, ensure the date string is found
              **within the same row or entry** as the person's name.
            - Apply the formatting rules above ONLY to explicitly found and correctly associated dates.
            - Extract both dates for `Term: ... to ...` pattern if both are explicit and
              associated with the current person.
          - **Key Examples**:
            - "Term Expires January 2027" -> `end_date`: {"data": "2027-01"}
            - "Serving through 2025" -> `end_date`: {"data": "2025"}
            - "Term: Jan 2023 to Dec 31, 2026" -> `start_date`: {"data": "2023-01"}, `end_date`: {"data": "2026-12-31"}
            - "Elected last year" -> `start_date`: null
            - "Term began on the usual date" -> `start_date`: null
            - "elected in Nov 2020, reelected Nov 2024" -> `start_date`: {"data": "2024-11"}
            - "term ending December 2028" -> `end_date`: {"data": "2028-12"}
            - "Elected Nov 2024 for term ending Dec 2028. Resigned April 15." -> (This person should NOT
              be in the output).
            - **Final Check**: Was the output date explicitly written in the text (or directly convertible via
              the Month YYYY rule) **and clearly associated with the correct individual**? If not, it MUST be null.
              No exceptions for inference or misattribution.
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
