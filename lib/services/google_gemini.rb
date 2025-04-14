require "core/city_manager"
require "utils/costs_helper"
require "pp"

module Services
  class GoogleGemini
    # MODEL = "gemini-2.5-pro-exp-03-25".freeze # FREE TIER
    MODEL = "gemini-2.0-flash".freeze # FREE TIER
    # MODEL = "gemini-1.5-pro".freeze
    # MODEL = "gemini-2.0-flash"
    BASE_URI = "https://generativelanguage.googleapis.com".freeze
    BASE_SLEEP = 5

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

        First, determine whether the content contains a directory or about page of elected official(s).
        If so, continue with the following instructions. If not, return an empty array.

        Your sole function is to extract information about elected officials
        listed on the following specific web page(s) based *only* on the content
        found there and format it strictly as JSON.

        **Target City:** #{city}

        Goal: Identify all people listed on the provided content who currently
        hold roles as elected officials in the city government.

        **Roles of Interest:** #{positions.join(", ")}
        (Also consider associated roles like: #{divisions.join(", ")})
        (Examples of role names: #{position_examples})

        Instructions:
        - For "llm_confidence", and "llm_confidence_reason",
          provide a number between 0 and 1, and an associated reason.
          How confident are you that the contact information
          is associated with #{person["name"]}? Provide the reason for your confidence.
        - For "proximity_to_name", provide a number of the distance
          between the contact information and the person's name in terms of word count.
        - Extract the name, phone number, email, website, and positions of the people listed in the content.
        - For start_term_date and end_term_date, only provide dates if they are explicitly stated or
          can be directly inferred with certainty—do not assume or estimate missing information.
        - start_term_date and end_term_date should be strings.
        - Only include an individual in the output array if their `name` can be successfully extracted from the content. If no name is found for a potential entry, omit that entry entirely.
        - If the content does not contain any information about elected officials, return an empty array.

        Return a JSON object where each person has the following properties:
        - name
          image (Extract the image URL from the <img> tag's src attribute.
                This will always be a relative URL starting with images/)
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
          website: <an object with the following properties:
            data: <string>
            llm_confidence: <number>
            llm_confidence_reason: <string>
            proximity_to_name: <number>
            markdown_formatting: {
              in_list: <boolean> # Whether the contact information is in a list
            }
          positions (an array of strings)
          start_term_date (string. The date the person has an active term for. Format: YYYY-MM, or YYYY-MM-DD)
          end_term_date (string. The date the person's term ends for their current position. Format: YYYY-MM, or YYYY-MM-DD)


        Here is the content:
        #{content}
      )

      request_origin = "#{state}_#{city}_gemini_#{MODEL}_extract_people"
      response = run_prompt(prompt, request_origin, city_council_url,
                            Shared::ResponseSchemas::GEMINI_PEOPLE_ARRAY_SCHEMA)

      # Filter out invalid people
      people = response.select do |person|
        Scrapers::Standard.valid_name?(person["name"]) &&
          person["positions"].present? && person["positions"].count.positive?
      end

      people.map do |person|
        Services::Shared::People.data_points_with_source(person, city_council_url)
        # Scrapers::Standard.normalize_source_person(person)
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
        based *only* on the content found there and format it strictly as JSON.

        **Target City:** #{city}
        **Person:** #{person["name"]}

        **Roles of Interest:** #{positions.join(", ")}
        (Also consider associated roles like: #{divisions.join(", ")})
        (Examples of role names: #{position_examples})

        Return object in JSON:
        name: <string> (Required)
        phone_numbers: <an array of objects with the following properties:
          data: <string>
          llm_confidence: <number>
          llm_confidence_reason: <string>
          proximity_to_name: <number>
          markdown_formatting: {
            in_list: <boolean> # Whether the contact information is in a list
          }
        emails: <an array of objects with the following properties:
          data: <string>
          llm_confidence: <number>
          llm_confidence_reason: <string>
          proximity_to_name: <number>
          markdown_formatting: {
            in_list: <boolean> # Whether the contact information is in a list
          }
        positions: <array of strings>
        start_term_date: <string> Format: YYYY-MM, or YYYY-MM-DD
        end_term_date: <string> Format: YYYY-MM, or YYYY-MM-DD

        **Instructions**
        - For "llm_confidence", and "llm_confidence_reason",
          provide a number between 0 and 1, and an associated reason.
          How confident are you that the contact information
          is associated with #{person["name"]}? Provide the reason for your confidence.
        - For "proximity_to_name", provide a number of the distance
          between the contact information and the person's name in terms of word count.

        **Content:** #{content}
      )

      # Create a mutable copy of the schema to modify it for the API call
      schema_for_api = Shared::ResponseSchemas::GEMINI_PERSON_SCHEMA.dup
      schema_for_api[:properties] = schema_for_api[:properties].dup # Duplicate nested properties hash
      schema_for_api[:properties].delete(:website) # Remove website property for this specific call

      request_origin = "#{state}_#{city}_gemini_#{MODEL}_get_person"
      extracted_person = run_prompt(prompt, request_origin, url, schema_for_api)

      return nil if extracted_person.nil?

      extracted_person = Services::Shared::People.data_points_with_source(extracted_person, url)
      # Scrapers::Standard.normalize_source_person(extracted_person)
    end

    def run_prompt(prompt, request_origin, request_url, schema_for_api)
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

        puts "Failed to parse JSON response from Gemini: #{json_output}" if parsed_response.nil?

        parsed_response
      else
        puts "Request failed. HTTP Status: #{response.code}"
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
