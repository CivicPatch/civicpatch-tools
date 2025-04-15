require "core/city_manager"
require "utils/costs_helper"
require "pp"
require_relative "shared/gemini_people"

module Services
  class GoogleGemini
    MODEL = "gemini-2.5-pro-exp-03-25".freeze # FREE TIER
    # MODEL = "gemini-2.0-flash".freeze # FREE TIER
    # MODEL = "gemini-1.5-pro".freeze
    # MODEL = "gemini-2.0-flash"
    BASE_URI = "https://generativelanguage.googleapis.com".freeze
    BASE_SLEEP = 5

    def initialize
      @api_key = ENV["GOOGLE_GEMINI_TOKEN"]
    end

    def fetch(state, city_entry, government_type)
      city = city_entry["name"]
      positions = Core::CityManager.get_position_roles(government_type)
      divisions = Core::CityManager.get_position_divisions(government_type)
      position_examples = Core::CityManager.get_position_examples(government_type)
      city_url = city_entry["website"]

      prompt = %(
        Act as a precise data extraction script using grounding capabilities.

        Your goal is to identify and extract information about current elected officials 
        for a specific city by first finding the relevant information online and then processing it.

        **Target City:** #{city}
        **Target City Website:** #{city_url}

        **Roles of Interest:** #{positions.join(", ")} // Example: City Council Member, Council President
        (Also consider associated roles like: #{divisions.join(", ")}) // Example: District 1, At-Large Position 8
        (Examples of role names: #{position_examples}) // Example: Councilmember, Councilor, Board Member

        Instructions:

        1.  **Find Information:** Use your grounding capabilities (Google Search) 
            to locate the most relevant and official current directory or 'about' page(s) 
            for elected officials holding the roles of interest in the target city government (#{city}).
        2.  **Verify Relevance:** Analyze the content retrieved via grounding. 
            Determine if it actually contains a directory or listing of the specified elected officials. 
            If no relevant officials or page is found, return an empty array `[]`.
        3.  **Extract Data:** If relevant officials are found, extract information for each person listed 
            based *only* on the content retrieved via grounding. Format the output strictly as a JSON array.
        4.  **Extraction Fields:**
            * `name`: Extract the full name. Only include an individual if their `name` can be successfully extracted.
            * `positions`: An array of strings listing the specific role(s) held by the person 
                (e.g., ["Council Member", "District 1"]).
            * `phone_number`: Extract the primary contact phone number.
            * `email`: Extract the primary contact email address.
            * `website`: CRITICALLY IMPORTANT - Extract the EXACT URL for the official's personal page or profile:
                - Do not modify, change or reconstruct URLs - use exactly what you find in the source
                - Copy the complete URL directly from the page's HTML or link elements
                - Include the full URL with domain (e.g., "https://my.spokanecity.org/citycouncil/members/john-smith")
                - If you're unsure about a URL, include it exactly as seen rather than guessing 
            * `term_date`: Extract if explicitly stated or directly inferable from the retrieved content. 
               Do not infer or estimate.
            * `source`: The URL where the information was found.
        5.  **Strict Formatting:** Adhere strictly to the JSON array format where each object represents one official 
            with the properties listed above.
            Return `[]` if no officials matching the criteria are found in the grounded content.

        **Website Extraction Examples:**
        - If a council member is listed on a directory page with a link to their profile, extract that profile URL as their website
        - If text like "[View John Smith's Page]" appears near a person's info, extract the linked URL
        - If an official's name or photo is clickable, extract the destination URL
        - Example: For "Mayor Lisa Brown", the website might be "https://mycity.gov/mayor/lisa-brown" or "https://mycity.gov/mayor/about"

        **Output Format:** Return JSON as follows.
        {
          "people": [
            {
            "name": "John Doe",
            "positions": ["Mayor", "Council Member"],
            "phone_number": "123-456-7890",
            "email": "test@example.com",
            "website": "https://example.com/about/john-doe",
            "term_date": "2024-01-01 to 2028-12-31" // Or "2024 to 2027", "2024-01 to 2028-12", "2024-01-01 to 2028-12-31",
            "source": "https://example.com/about" // The URL where the information was found
            }
            // ... more objects for other officials
          ]
        }
      )

      request_origin = "#{state}_#{city}_gemini_#{MODEL}_extract_people"
      response = run_prompt(prompt, request_origin)

      return [] if response.nil? || response["people"].nil? || !response["people"].is_a?(Array)

      # Filter out invalid people
      people = response["people"].select do |person|
        Scrapers::Standard.valid_name?(person["name"]) &&
          person["positions"].present? && person["positions"].count.positive?
      end

      people.map do |person|
        Services::Shared::GeminiPeople.format_raw_data(person)
      end
    end

    def run_prompt(prompt, request_origin)
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
        },
        tools: [
          {
            googleSearch: {}
          }
        ]
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
          puts "Google Gemini is running..."
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

        json_output = response_candidate["content"]["parts"].first["text"]

        cleaned_json_output = json_output.gsub("```json", "").gsub("```", "")

        parsed_response = begin
          JSON.parse(cleaned_json_output)
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
      nil
    end
  end
end
