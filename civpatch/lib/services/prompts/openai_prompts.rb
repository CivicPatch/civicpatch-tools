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
        current_date = Time.now.strftime("%Y-%m-%d")

        content_type = if person_name.present?
                         "First, determine if the content contains information about the target person: #{person_name}."
                       elsif maybe_target_people.present? && maybe_target_people.count.positive?
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
                       else
                         %(Your primary task is to identify and extract information for the members of
                         the primary governing body (e.g., Town Council, City Council, Select Board,
                         Board of Aldermen, Commissioners) of the target municipality found within the provided content.
                         Be cautious with other municipal boards (e.g., Planning Board, Zoning Board,
                         Conservation Commission, etc.) -- they are not the primary governing body.)
                       end

        system_instructions = <<~INSTRUCTIONS
          You are an expert data extractor focused on accuracy.

          #{content_type} If not, return an empty JSON array `[]`.

          Target Person (if applicable): #{person_name}
          Target Municipality: #{municipality_entry["name"]}, #{state}
          Target roles: #{roles.join(", ")}
          Target divisions: #{division_names.join(",")}

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

          Extraction Guidelines:
          - Roles extraction:
            - Extract roles that match the **target roles** provided (e.g., #{roles.join(", ")}).
            - If a role includes additional descriptors or variations, normalize it to the closest matching target role when possible.
              - Example: "Vice President" under a governing body → Normalize to the closest matching target role, such as "Council Vice President" or "Commissioner Vice President."
            - If a role cannot be normalized to a target role but is clearly valid (e.g., "Vice President"), extract it as-is.
            - Use the governing body or surrounding context to determine the correct role for ambiguous titles.
              - Example: If "Vice President" is listed under "Council Members," infer it as "Council Vice President."
              - Example: If "Vice President" appears without clear context, extract it as "Vice President."
            - Provide a confidence score (`llm_confidence`) and a brief reason for the inference or extraction.
            - Include only active roles (today is #{current_date}).

          - Divisions:
            - Extract divisions if explicitly mentioned and relevant to the person's role.
            - Examples:
              - "Citywide Position 7" → Extract as "Citywide" and "Position 7."
              - "At-Large Position 2" → Extract as "At-Large" and "Position 2."
            - Do not infer divisions if they are not explicitly stated.

          - General Guidelines:
            - Merge details for the same person into a single record.
            - Assign confidence (0-1 scale) and provide a brief reason for each field's data.
            - Extract full names only (e.g., "John Smith," not "Mayor John Smith"). Titles belong in the roles field.
            - Ensure extracted data is accurate and relevant to the governing body or target roles.
          - Image: Extract URL of portrait/headshot near name. Ignore logos, banners, icons. Check alt text but prioritize proximity/style.
          - Contact Details (Phone/Email/Website):
            - Associate details logically if near the person's name/section.
            - Pick the most relevant contact detail if multiple are present.
            - Phone numbers:
              - Extract number after labels like "Office:", "Cell:", "Mobile:", "Direct:", "Home:". Exclude "Fax:". Format numbers simply.
            - Markdown Links: Extract email/phone from the VISIBLE TEXT of links like `[TEXT](...)`, ignore the target URL.
            - `website` data MUST be a valid http/https URL. Prefer profile pages. EXCLUDE mailto:, tel:.
            - `email` data should ONLY contain email addresses.
          - Term Dates (`start_date`, `end_date`):
            - Extract start_date and end_date in YYYY, YYYY-MM, or YYYY-MM-DD format.
            - Acceptable date phrases include:
              - “Elected [date]”, “Appointed [date]”, “Term: [date1] to [date2]”, “Since [date]”.
              - For vague phrases like "Spring 2025", extract the year only.
            - If more than one term is mentioned, extract the most recent term dates.
            - Examples:
              - "Elected Nov 2024 for term ending Dec 2028" -> start_date: "2024-11", end_date: "2028-12"
              - "Served January 2018 until December 2021 - Re-elected and serving January 2022 and until December 2025" -> start_date: "2022-01", end_date: "2025-12"
              - "Elected in 2017 and re-elected in 2021 for the 2022-2025 term." -> start_date: "2022", end_date: "2025"

          **FINAL MANDATORY CHECK**: Review your entire response for accuracy before submitting,
            paying close attention to the role inference, date extraction, and term identification rules.
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
