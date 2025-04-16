module Services
  module Shared
    class LlmPrompts
      def self.gemini_generate_city_directory_prompt(state, city_entry, government_type, content)
        city_name = city_entry["name"]
        positions = Core::CityManager.get_position_roles(government_type)
        divisions = Core::CityManager.get_position_divisions(government_type)
        position_examples = Core::CityManager.get_position_examples(government_type)
        current_date = Date.today.strftime("%Y-%m-%d")

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
        - phone_number: {data, llm_confidence, llm_confidence_reason, proximity_to_name, markdown_formatting: {in_list}}
        - email: {data, llm_confidence, llm_confidence_reason, proximity_to_name, markdown_formatting: {in_list}}
        - website: {data, llm_confidence, llm_confidence_reason, proximity_to_name, markdown_formatting: {in_list}}
        - term_date: {data, llm_confidence, llm_confidence_reason, proximity_to_name, markdown_formatting: {in_list}}
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
        - For "proximity_to_name": Word count distance between info and person's name
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

        Here is the content of the city page:
        #{content}
       )
      end

      def self.gemini_generate_city_profile_prompt(government_type, person, content)
        positions = Core::CityManager.get_position_roles(government_type)
        divisions = Core::CityManager.get_position_divisions(government_type)
        position_examples = Core::CityManager.get_position_examples(government_type)

        %(
        You are an expert data extractor.

        You should be returning a JSON object with the following properties:
        You are looking for content related to #{person["name"]}

        Return a JSON object with the following properties:
        name
        positions (An array of strings)
        image (Extract the image URL from the <img> tag's src attribute. This will always be a relative URL starting with images/)
        phone_number: <an object with the following properties:
          data: <string>
          llm_confidence: <number>
          llm_confidence_reason: <string>
          proximity_to_name: <number>
          markdown_formatting: {
            in_list: <boolean> # Whether the contact information is in a list
          }
        email: <an object with the following properties:
          data: <string>
          llm_confidence: <number>
          llm_confidence_reason: <string>
          proximity_to_name: <number>
          markdown_formatting: {
            in_list: <boolean> # Whether the contact information is in a list
          }
        term_date: <an object with the following properties>
          data: <string> # The date the person has an active term for. Format: YYYY to YYYY, YYYY-MM to YYYY-MM, or YYYY-MM-DD to YYYY-MM-DD
          llm_confidence: <number>
          llm_confidence_reason: <string>
          proximity_to_name: <number>
          markdown_formatting: {
            in_list: <boolean> # Whether the contact information is in a list
          }

        Notes:
        - For "llm_confidence", and "llm_confidence_reason",#{" "}
          provide a number between 0 and 1, and an associated reason.#{" "}
          How confident are you that the contact information#{" "}
          is associated with #{person["name"]}? Provide the reason for your confidence.
        - For "proximity_to_name", provide a number of the distance
          between the contact information and the person's name in terms of word count.
        - Extract only the contact information associated with the person. Do not return general info.
        - For term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
        - For the "positions" field, split the positions into an array of strings.
          The main positions we are interested in are #{positions.join(", ")}
          Positions may also be associated with titles like #{divisions.join(", ")}
          where the positions are attached with vairous numbers or words.
        - Today is #{current_date}. Ensure that only active positions are included, and#{" "}
          exclude any positions that are not currently held or are no longer active.
        Position Examples:
          #{position_examples}

        Here is the content:
        #{content}
        )
      end
    end
  end
end
