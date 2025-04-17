module Services
  module Shared
    class LlmPrompts
      def self.gemini_generate_city_directory_prompt(state, city_entry, government_type, content)
        city_name = city_entry["name"]
        positions = Core::CityManager.get_position_roles(government_type)
        divisions = Core::CityManager.get_position_divisions(government_type)
        position_examples = Core::CityManager.get_position_examples(government_type)
        current_date = Date.today.strftime("%Y-%m-%d")

        # NOTE: omitting proximity_to_name from the response because there is a bug in the LLM
        %(
        You are an expert data extractor.

        First, determine if the content contains elected officials' information. If not, return an empty array.

        Target City: #{city_name}, #{state}
        Key roles: #{positions.join(", ")}
        Associated divisions: #{divisions.join(",")}
        Examples: #{position_examples}

        Return a JSON object with people, each having:
        - name: Full name only (not titles)
        - image: URL from <img> tag (starting with "images/")
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
              "image": "images/12341324132.jpg",
              "phone_number": {"data": "123-456-7890", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under Contact.", "proximity_to_name": 50, "markdown_formatting": {"in_list": true}},
              "email": {"data": "john.doe@example.com", "llm_confidence": 0.95, "llm_confidence_reason": "Directly associated with name.", "proximity_to_name": 10, "markdown_formatting": {"in_list": false}},
              "website": {"data": "https://example.com/john-doe", "llm_confidence": 0.95, "llm_confidence_reason": "Found under header", "markdown_formatting": {"in_list": true}},
              "positions": ["Mayor", "Council Member"],
              "term_date": {"data": "2022-01-01 to 2022-12-31", "llm_confidence": 0.95, "llm_confidence_reason": "Listed under header.", "proximity_to_name": 35, "markdown_formatting": {"in_list": true}}
            }
          ]
        }

        Guidelines:
        - For "llm_confidence": Use 0-1 scale with reason for your confidence
        - Extract only person-specific information, not general contact info
        - Omit missing fields except for "name"
        - For positions: Include only active roles (today is #{current_date})
        - Name extraction: Extract full names ONLY, not titles
          - CORRECT: "Lisa Brown" (not "Mayor Brown" or "Mayor Lisa Brown")
          - Titles belong in positions array, not in names
        - Website extraction:
          - Prioritize person-specific pages over landing pages
          - Consider links associated with names/photos
          - Prefer deeper paths and "/about" pages when available
        - Today is #{current_date}. Ensure that only active positions are included, and
          exclude any positions that are not currently held or are no longer active.
        Here is the content of the city page:
        #{content}
       )
      end
    end
  end
end
