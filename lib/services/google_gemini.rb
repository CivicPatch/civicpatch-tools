module Services
  class GoogleGemini
    MODEL = "gemini-2.5-pro-exp-03-25".freeze
    BASE_URI = "https://generativelanguage.googleapis.com".freeze
    BASE_SLEEP = 5

    def initialize
      @api_key = ENV["GOOGLE_GEMINI_TOKEN"]
    end

    def get_city_people(city, url)
      prompt = %(
        Give me city officials contact info for
        #{city} using #{url} Do this in YAML.

        Notes:
        * Return the values in YAML.
        * Don't return anything that isn't in YAML.
        * Don't list council members whose terms have ended.

        The YAML should be in this format, in an array:
        - name: <string>
          phone_number: <string> Format: (123) 456-7890
          email: <string>
          positions: [<an array of strings>]
          start_term_date (string. The date the person started their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
          end_term_date (string. The date the person ended their term. Format: YYYY, YYYY-MM, or YYYY-MM-DD)
          website: (Provide the absolute URL)

        Basic rules:
        - Extract only the contact information associated with the person. Do not return general info.
        - City council members and city leaders should all be human beings with a name and at least one piece of contact field.
        - Output the results in YAML format. For any fields not provided in the content, return an empty string, except for 'name' which is required.
        - If you cannot find any relevant information, return YAML as empty array.

        - To make it on the people list, they must be associated with either "position" OR "position_misc
        - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
          They should be strings.
        - For the "positions" field, split the positions into an array of strings.
          Some typical positions are #{positions.join(", ")}
          Preserve non-numeric names as they are.
          Do not list previous positions if their terms have ended.
          People can have multiple positions and roles.
          Examples:

          Input: "council member ward 3" → Output: `["council member", "ward 3"]`
          Input: "ward #3" → Output: `["ward 3"]`
          Input: "mayor, 3rd district" → Output: `["mayor", "ward 3"]`
          Input: "seat 5" → Output: `["council member", "seat 5"]`
          Input: "council vice president" → Output: `["council vice president"]`
          Input: "mayor" → Output: `["mayor"]`
          Input: "deputy mayor" → Output: `["deputy mayor"]`
          Input: "mayor position 7" → Output: `["mayor", "position 7"]`
          Input: "council president" → Output: `["council president"]`
          Input: "position 8 at-large" → Output: `["position 8", "at-large"]`
          Input: "position no 8" → Output: `["position 8"]`
      )

      response = run_prompt(prompt)
      response.map do |person|
        person["sources"] = [url]
        Scrapers::Standard.normalize_source_person(person)
      end
    end

    def run_prompt(prompt)
      retry_attempts = 0
      url = "#{BASE_URI}/v1beta/models/#{MODEL}:generateContent?key=#{@api_key}"

      payload = {
        contents: [{
          parts: [{
            text: prompt
          }]
        }]
      }.to_json

      options = {
        body: payload,
        headers: {
          "Content-Type" => "application/json"
        },
        timeout: 60
      }

      response = nil
      progress_thread = Thread.new do
        loop do
          print "."
          sleep 2
        end
      end

      begin
        response = HTTParty.post(url, options)
      ensure
        progress_thread.kill
        puts "\n" # Add a newline after the dots
      end

      if response.success?
        # TODO: needs more robustness
        response_candidate = response["candidates"].first
        yaml_string = response_candidate["content"]["parts"].first["text"]

        Utils::YamlHelper.yaml_string_to_hash(yaml_string)
      else
        puts "Request failed. HTTP Status: #{response.code}"
        nil
      end
    rescue StandardError => e
      puts e.message
      if retry_attempts < MAX_RETRIES
        sleep_time = BASE_SLEEP**retry_attempts + rand(0..1)
        puts "Might be running into rate limits. Retrying in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
        sleep sleep_time
        retry_attempts += 1
        retry
      else
        puts "Too many requests. Max retries reached for Google Gemini."
      end
    end
  end
end
