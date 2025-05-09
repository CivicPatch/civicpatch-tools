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
        This total number includes the Mayor (only if available).

        Create a JSON object with a single top-level key "people". The value of "people" must be an array.

        This array must contain exactly the total number of elected officials determined in step 1.

        Within the array, include one entry for the Mayor (only if available)
        and the remaining entries for "Council Member" positions.

        For each entry in the array, provide the current elected official's name
        only if you are highly certain based on your training data or search results.

        If you are not highly certain of the current name for any specific position,
        or if the information might be outdated or incomplete, set the 'name' field to null for that entry.

        Return ONLY the following JSON structure with no other text:
        {
          "people": [{
            "name": The official's name (string) or null.
            "positions": The position held (array of strings), which should be either "Mayor" or "Council Member" (or equivalent).
          }],
          "notes": "Notes about the search and the results"
        }

        IMPORTANT: I need ONLY the JSON object as your response, with NO additional text, explanation, or markdown formatting. Do not include any text before or after the JSON object. Your entire response should be a valid JSON object that can be directly parsed.
      )
      end

      def self.gemini_generate_municipal_directory_prompt(municipality_context, content, person_name = "")
        state = municipality_context[:state]
        municipality_name = municipality_context[:municipality_entry]["name"]
        government_type = municipality_context[:government_type]
        municipality_config = Core::CityManager.get_config(government_type)
        positions = municipality_config["positions"]
        divisions = positions.flat_map { |position| position["divisions"] }
        position_examples = municipality_config["position_examples"]
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
        - Positions extraction:
          - **CRITICAL**: Extract roles that EXACTLY MATCH or are CLEAR SYNONYMS for the
            **Target Municipal Roles** and **Examples** provided, AND are **currently active** as of #{current_date}.
          - **Handling Resignations/Vacancies**: If the text explicitly states that a person has **resigned, vacated their position, is deceased, or their position is otherwise noted as vacant (e.g., "applications being accepted")**, DO NOT include them as a current office holder or extract their position, even if a future term date is also mentioned. The statement of resignation or vacancy takes precedence over listed term dates for determining current active status.
          - **Check for Past Dates**: Before extracting a specific position title (e.g., "Council President", "Chair"), examine the surrounding text for associated dates or date ranges (e.g., "served as ... from 2011-2012", "President in 2015", "(2011-2012)"). If such dates clearly indicate the role was held **only in the past** and is not the person's current role, **DO NOT extract that specific position title.** Focus only on roles the person currently holds according to the text.
          - **EXCLUDE**: Do NOT extract roles that are clearly advisory, honorary, student/youth positions
            (e.g., "Youth Councilor", "Student Representative"),
            or non-voting unless they are explicitly listed in the Target Municipal Roles.
            Focus on the primary elected/appointed governing body members.
          - Include only active roles (today is #{current_date}).
          - Include both the role and any associated division (e.g., "Council Member, District 3").
          - **Avoid Redundant Phrasing in Positions**: If similar terms describing the same core role
            (e.g., "Council Member," "Councilor") are found associated with the same division (like Ward, District, Seat),
            extract only the most complete or primary term used in the source text. Do not concatenate these similar terms
            for a single position. For instance, for "Ward 3 Councilor," prefer "Councilor, Ward 3" or
            "Council Member, Ward 3" (if "Council Member" is the standard term for that role type),
            but not "Council Member, Ward 3 Councilor."
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
            - If the source text explicitly provides a date as `YYYY`, `YYYY-MM`, or `YYYY-MM-DD`, output that exact string.
            - If the source text explicitly provides a date as `Month YYYY` (e.g., "January 2027"),
              convert it to `YYYY-MM` (e.g., "2027-01").
            - If the source text provides an explicit date in any other format, treat it as not found and output null.
          - **Identifying the Correct Start Date (if multiple 'elected' dates)**:
            - If multiple "elected" or "reelected" dates are mentioned for a person, use the date associated with the
              **most recent** election/re-election for the `start_date`.
            - Example: "elected in November 2020 and was reelected in November 2024" → `start_date` should
              be based on "November 2024".
          - **Locating Dates**:
            - Use keywords (`start_date` keywords: 'Elected:', 'Elected in', 'Appointed:', 'Term Began:', 'Sworn In:', 'Serving Since:', 'First Elected:', 'Took Office', 'Started', 'Since:', 'Beginning', 'Commenced', 'Assumed Office:', 'Joined Council', 'Began Service', `end_date` keywords: 'Term Expires:', 'Term Ends:', 'Term ending', 'Serving Until:', 'Until:', 'Expires', 'Ending', 'Through', 'Next Election:', 'End of Term:') and patterns (`Term: [Date1] to [Date2]`, `Term: YYYY-YYYY`) to find potential explicit date strings **that are clearly associated with the specific person being processed.**
            - When multiple `start_date` keywords like "elected" or "reelected" are found,
              apply the "Identifying the Correct Start Date" rule above.
            - When extracting from tables, ensure the date string is found
              **within the same row or entry** as the person's name.
            - Apply the formatting rules above ONLY to explicitly found and correctly associated dates.
            - Extract both dates for `Term: ... to ...` pattern if both are explicit and associated with the current person.
          - **Key Examples**:
            - "Term Expires January 2027" -> `end_date`: {"data": "2027-01"}
            - "Serving through 2025" -> `end_date`: {"data": "2025"}
            - "Term: Jan 2023 to Dec 31, 2026" -> `start_date`: {"data": "2023-01"}, `end_date`: {"data": "2026-12-31"}
            - "Elected last year" -> `start_date`: null
            - "Term began on the usual date" -> `start_date`: null
            - "elected in Nov 2020, reelected Nov 2024" -> `start_date`: {"data": "2024-11"}
            - "term ending December 2028" -> `end_date`: {"data": "2028-12"}
            - "Elected Nov 2024 for term ending Dec 2028. Resigned April 15." -> (This person should NOT
              be in the output, or if forced to output, all their fields like positions and dates should be null/empty,
              with a reason citing the resignation).
            - **Final Check**: Was the output date explicitly written in the text (or directly convertible via
              the Month YYYY rule) **and clearly associated with the correct individual**? If not, it MUST be null.
              No exceptions for inference or misattribution.
        - Today is #{current_date}. Context only, do not use for date calculation.
        - Association: Contact details (phone, email) listed under common headings like 'Contact' or 'Contact Us'
          that appear structurally close (e.g., immediately following section) to a specific person's name or section
          should be associated with that person unless the text clearly indicates otherwise (e.g., 'General City Contact').
          **When processing tabular data, ensure all extracted fields for a single person (name, positions, dates, etc.)
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
