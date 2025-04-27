module Services
  module Shared
    class LlmPrompts
      def self.gemini_generate_municipal_directory_prompt(state, city_entry, government_type, content, person_name = "")
        city_name = city_entry["name"]
        positions = Core::CityManager.get_position_roles(government_type)
        divisions = Core::CityManager.get_position_divisions(government_type)
        position_examples = Core::CityManager.get_position_examples(government_type)
        current_date = Date.today.strftime("%Y-%m-%d")

        content_type = if person_name.present?
                         "First, determine if the content contains information about the target person."
                       else
                         "First, determine if the content contains a directory of elected officials."
                       end

        # NOTE: omitting proximity_to_name from the response because there is a bug in the LLM
        %(
        You are an expert data extractor.

        #{content_type}
        If not, return an empty array.

        #{person_name.present? ? "Target Person: #{person_name}" : ""}
        Target City: #{city_name}, #{state}
        Target Municipal Roles: #{positions.join(", ")}
        Associated divisions: #{divisions.join(",")}
        Examples: #{position_examples}

        Return a JSON object with people, each having:
        - name: Full name only (not titles)
        - phone_number: {data, llm_confidence, llm_confidence_reason, markdown_formatting: {in_list}}
        - email: {data, llm_confidence, llm_confidence_reason, markdown_formatting: {in_list}}
        - website: {data, llm_confidence, llm_confidence_reason, markdown_formatting: {in_list}}
        - term_date: {data, llm_confidence, llm_confidence_reason, markdown_formatting: {in_list}}
        - positions: [array of strings]

        Format example:
        {
          "people": [
            {
              "name": "John Doe",
              "phone_number": {"data": "123-456-7890", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under Contact.", "proximity_to_name": 50, "markdown_formatting": {"in_list": true}},
              "email": {"data": "john.doe@example.com", "llm_confidence": 0.95, "llm_confidence_reason": "Directly associated with name.", "proximity_to_name": 10, "markdown_formatting": {"in_list": false}},
              "website": {"data": "https://example.com/john-doe", "llm_confidence": 0.95, "llm_confidence_reason": "Found under header", "markdown_formatting": {"in_list": true}},
              "positions": ["Mayor", "Council Member"],
              "term_date": {"data": "2022-01-01 to 2022-12-31", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under header.", "proximity_to_name": 35, "markdown_formatting": {"in_list": true}}
            },
            {
              "name": "Jane Smith",
              "phone_number": {"data": "(987) 654-3210", "llm_confidence": 0.90, "llm_confidence_reason": "Extracted from markdown link text like [(987) 654-3210]()", "markdown_formatting": {"in_list": false}},
              "email": {"data": "jane.smith@example.gov", "llm_confidence": 0.92, "llm_confidence_reason": "Found under 'Contact Us' section near name.", "markdown_formatting": {"in_list": false}},
              "positions": ["Council President"]
            }
          ]
        }

        Guidelines:
        - For "llm_confidence": Use 0-1 scale with reason for your confidence
        - For positions:
          - **CRITICAL**: Extract ONLY roles matching or functionally equivalent to the
            **Target Municipal Roles** and **Examples** provided
            (e.g., Mayor, Council Member, City Manager, Alderman).
            Focus on municipal legislative and executive positions.
          - **EXCLUDE** judicial roles (Judge, Magistrate), administrative roles
            (Clerk, Treasurer, Assessor, Recorder unless listed in Target Municipal Roles),
            county/state/federal officials unless they also hold a key municipal role, and
            appointed (non-elected) staff unless specifically targeted.
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
          - Prefer shorter, cleaner URLs over ones with many complex query parameters unless clearly necessary for the specific person's profile page.
        - Email extraction:
          - Extract email addresses found directly in the text.
          - Also extract emails formatted as Markdown link *text*,
            like `[email@example.com]()` or `[email@example.com](some-link)`.
            Extract the email address shown in the brackets.
          - Place extracted emails ONLY in the "email" field, NEVER in the "website" field.
        - Today is #{current_date}. Ensure that only active positions are included, and
          exclude any positions that are not currently held or are no longer active.
        - Association: Contact details (phone, email) listed under common headings like 'Contact' or 'Contact Us' that appear structurally close (e.g., immediately following section) to a specific person's name or section should be associated with that person unless the text clearly indicates otherwise (e.g., 'General City Contact').
        - Ensure only ONE entry exists per unique person's name. Merge all extracted details for the same person into a single record

        Here is the content:
        #{content}
       )
      end
    end
  end
end
