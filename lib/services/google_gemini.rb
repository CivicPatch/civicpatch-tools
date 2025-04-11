require "core/city_manager"
require "utils/yaml_helper"
require "utils/costs_helper"

module Services
  class GoogleGemini
    # MODEL = "gemini-2.5-pro-exp-03-25".freeze # FREE TIER
    MODEL = "gemini-1.5-flash".freeze # FREE TIER
    # MODEL = "gemini-1.5-pro".freeze
    # MODEL = "gemini-2.0-flash"
    BASE_URI = "https://generativelanguage.googleapis.com".freeze
    BASE_SLEEP = 5

    # Define the desired JSON output schema (OpenAPI format) as a constant
    PERSON_SCHEMA = {
      type: :object,
      properties: {
        name: { type: :string },
        phone_number: { type: :string },
        email: { type: :string },
        website: { type: :string },
        positions: {
          type: :array,
          items: { type: :string }
        },
        start_term_date: { type: :string },
        end_term_date: { type: :string }
      },
      required: ["name"] # Enforce that name is required
    }.freeze # Freeze the constant for immutability

    # Define the schema for an ARRAY of person objects
    PEOPLE_ARRAY_SCHEMA = {
      type: :array,
      items: PERSON_SCHEMA # Each item in the array should follow PERSON_SCHEMA
    }.freeze

    def initialize
      @api_key = ENV["GOOGLE_GEMINI_TOKEN"]
    end

    def extract_city_people(state, city_entry, content_file, city_council_url)
      city = city_entry["name"]
      content = File.read(content_file)
      positions = Core::CityManager.get_position_roles("mayor_council")
      divisions = Core::CityManager.get_position_divisions("mayor_council")
      position_examples = Core::CityManager.get_position_examples("mayor_council")

      prompt = %(
        Act as a precise data extraction script.
        Your sole function is to extract information about elected officials
        listed on the following specific web page(s) based *only* on the content
        found there and format it strictly as YAML.

        **Target City:** #{city}

        Goal: Identify all people listed on the provided content who currently
        hold roles as elected officials in the city government.

        **Roles of Interest:** #{positions.join(", ")}
        (Also consider associated roles like: #{divisions.join(", ")})
        (Examples of role names: #{position_examples})

        Instructions:
        - Extract the name, phone number, email, website, and positions of the people listed in the content.
        - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
        - start_term_date and end_term_date should be strings.
        - Only include an individual in the output array if their `name` can be successfully extracted from the content. If no name is found for a potential entry, omit that entry entirely.
        - If the content does not contain any information about elected officials, return an empty array.

        YAML Output Format (an array of objects):
        ```yaml
        - name: <string> (Required)
        - phone_number: <string>
        - email: <string>
        - positions: <array of strings>
        - start_term_date: <string>
        - end_term_date: <string>
        - website: <string>
        ```

        Here is the content:
        #{content}
      )

      request_origin = "#{state}_#{city}_gemini_#{MODEL}_extract_people"
      response = run_prompt(prompt, request_origin, PEOPLE_ARRAY_SCHEMA)

      response.map do |person|
        person["sources"] = [city_council_url]
        Scrapers::Standard.normalize_source_person(person)
      end
    end

    def extract_person_information(state, city_entry, person, content_file, url)
      content = File.read(content_file)
      positions = Core::CityManager.get_position_roles("mayor_council")
      divisions = Core::CityManager.get_position_divisions("mayor_council")
      position_examples = Core::CityManager.get_position_examples("mayor_council")
      city = city_entry["name"]

      prompt = %(
        Act as a precise data extraction script.
        Your sole function is to extract information about a specific person
        based *only* on the content found there and format it strictly as YAML.

        **Target City:** #{city}
        **Person:** #{person["name"]}

        **Roles of Interest:** #{positions.join(", ")}
        (Also consider associated roles like: #{divisions.join(", ")})
        (Examples of role names: #{position_examples})

        Instructions:
        - Extract the name, phone number, email, website, and positions of the people listed in the content.
        - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
        - start_term_date and end_term_date should be strings.
        - Only include an individual in the output if their `name` can be successfully extracted from the content. If no name is found for a potential entry, omit that entry entirely.
        - If the content does not contain any information about elected officials, return an empty object {}.

        **Content:** #{content}
      )

      # Create a mutable copy of the schema to modify it for the API call
      schema_for_api = PERSON_SCHEMA.dup
      schema_for_api[:properties] = schema_for_api[:properties].dup # Duplicate nested properties hash
      schema_for_api[:properties].delete(:website) # Remove website property for this specific call

      request_origin = "#{state}_#{city}_gemini_#{MODEL}_get_person"
      extracted_person = run_prompt(prompt, request_origin, schema_for_api)

      puts "EXTRACTED PERSON: #{extracted_person.inspect}"

      extracted_person["website"] = url
      extracted_person["sources"] = [url]
      Scrapers::Standard.normalize_source_person(extracted_person)
    end

    # def get_city_people(state, city_entry, roster_urls)
    #  puts "roster urls: #{roster_urls}"
    #  city = city_entry["name"]

    #  positions = Core::CityManager.get_position_roles("mayor_council")
    #  divisions = Core::CityManager.get_position_divisions("mayor_council")
    #  position_examples = Core::CityManager.get_position_examples("mayor_council")
    #  prompt = %(
    #    Act as a precise data extraction script.
    #    Your sole function is to extract information about elected officials
    #    listed on the following specific web page(s) based *only* on the content
    #    found there and format it strictly as YAML.

    #    **Target City:** #{city}
    #    **Source URL(s):** #{roster_urls}

    #    Goal: Identify all people listed on the provided page(s) who currently hold relevant positions in the city's government.

    #    **Roles of Interest:** #{positions.join(", ")}
    #    (Also consider associated roles like: #{divisions.join(", ")})
    #    (Examples of role names: #{position_examples})

    #    Instructions:
    #    1. Access and carefully parse the content only from the provided Source URL(s).
    #    2. Crucially: Do NOT use any external knowledge, web searches, prior training data,
    #        or information from sources other than the exact URL(s) provided.
    #        Your knowledge is limited strictly to the content on the page(s).
    #    3. Identify any GENERAL contact information (office phone, office email,
    #        main department/city website) listed on the page for the Mayor/Council office.
    #        Store this general information temporarily.
    #    4. Identify individuals currently holding one or more Positions of Interest.
    #       Exclude former officials or those whose terms are clearly marked as ended on the page.
    #    5. For each such qualified individual:
    #        * Extract their `name` exactly as listed.
    #        * Extract their DIRECT `phone_number` only if a specific phone number is
    #          explicitly listed for that individual on the page. Use `""` if not found.
    #        * Extract their DIRECT `email` only if a specific email address is explicitly listed
    #          for that individual on the page. Use `""` if not found.
    #        * Extract their exact *current* `role` or `title` as listed on the page (e.g., "Mayor", "Seat 1", "Council Member", "Ward 3").
    #        Store these as an array of strings under the 'positions' key.
    #        * Extract `start_term_date` and `end_term_date` only if explicitly stated on the page
    #          for that person. Do not calculate or infer dates. Use `""` if not found.
    #        * Extract an individual DIRECT `website`/profile link *ONLY* if a unique URL for that specific person is clearly
    #          and unambiguously listed immediately next to or grouped with their name/details on the page.
    #          Do NOT infer, guess, or construct URLs.
    #          Do NOT use URLs found elsewhere on the page unless directly tied to the individual.
    #          Use the full absolute URL. Use `""` if not found.
    #    6. Fallback for General Contact Info: After processing an individual according to step 5,
    #       check if their `phone_number`, `email`, AND `website` fields are ALL `""`. If they are, then populate the
    #       `office_phone_number`, `office_email`, and `office_website` fields for that individual using the
    #       GENERAL contact information identified in step 3 (if any was found).
    #       If no general contact info was found in step 3, these office fields should also be `""`.
    #       If any of the direct `

    def run_prompt(prompt, request_origin, schema_for_api)
      retry_attempts = 0
      url = "#{BASE_URI}/v1beta/models/#{MODEL}:generateContent?key=#{@api_key}"

      payload = {
        contents: [{
          parts: [{
            text: prompt
          }]
        }],
        generationConfig: {
          temperature: 0,
          responseMimeType: "application/json",
          responseSchema: schema_for_api
        }
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
        usage = response["usageMetadata"]
        input_tokens_num = usage["promptTokenCount"]
        candidates_token_num = usage["candidatesTokenCount"]
        thoughts_token_num = usage["thoughtsTokenCount"].to_i # Diff models might not support thoughts

        Utils::CostsHelper.log_llm_cost(
          request_origin,
          "google_gemini",
          input_tokens_num,
          candidates_token_num + thoughts_token_num,
          MODEL
        )

        # TODO: needs more robustness
        response_candidate = response["candidates"].first

        # The response part should now be structured JSON due to response_mime_type
        json_output = response_candidate["content"]["parts"].first["text"]

        parsed_response = begin
          JSON.parse(json_output)
        rescue StandardError
          nil
        end # Use JSON.parse

        if parsed_response.nil?
          puts "Failed to parse JSON response from Gemini: #{json_output}"
          File.write("chat.txt", "RAW NON-JSON RESPONSE: #{json_output}", mode: "a")
        end

        # Log request/response
        File.write("chat.txt", "REQUEST", mode: "a")
        File.write("chat.txt", prompt, mode: "a")
        File.write("chat.txt", "PARSED RESPONSE", mode: "a")
        File.write("chat.txt", parsed_response.inspect, mode: "a")
        parsed_response
      else
        puts "Request failed. HTTP Status: #{response.code}"
        File.write("chat.txt", "REQUEST FAILED: #{response.code}", mode: "a")
        File.write("chat.txt", response.inspect, mode: "a")
        nil
      end
    rescue StandardError => e
      puts "RESPONSE: #{response.inspect}"
      puts e.message
      puts e.backtrace
      if retry_attempts < MAX_RETRIES # Check if MAX_RETRIES is defined
        sleep_time = BASE_SLEEP**retry_attempts + rand(0..1)
        puts "Might be running into rate limits. Retrying in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
        sleep sleep_time
        retry_attempts += 1
        retry
      else
        puts "Too many requests. Max retries reached for Google Gemini."
      end
      nil # Return nil on unrecoverable error
    end
  end # End of GoogleGemini class
end # End of Services module
