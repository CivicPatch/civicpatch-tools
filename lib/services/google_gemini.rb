# frozen_string_literal: true

require "core/city_manager"
require "utils/costs_helper"
require "pp"
require_relative "shared/gemini_prompts"
require "utils/name_helper"

module Services
  class GoogleGemini
    MAX_RETRIES = 5
    # MODEL = "gemini-2.5-pro-exp-03-25".freeze
    MODEL = "gemini-2.5-flash-preview-04-17"
    # MODEL = "gemini-2.0-flash".freeze
    # MODEL = "gemini-1.5-pro".freeze
    BASE_URI = "https://generativelanguage.googleapis.com"
    BASE_SLEEP = 5

    def initialize
      @api_key = ENV["GOOGLE_GEMINI_TOKEN"]
    end

    def search_for_people(municipality_context)
      state = municipality_context[:state]
      municipality_entry = municipality_context[:municipality_entry]

      prompt = Services::Shared::GeminiPrompts
               .gemini_generate_search_for_people_prompt(state, municipality_entry)

      request_origin = "#{state}_#{municipality_entry["name"]}_gemini_#{MODEL}_search_for_people"
      response = run_prompt(prompt, request_origin, with_search: true)

      return nil if response.blank?

      response
    end

    def extract_city_people(municipality_context, content_file, url, person_name = "")
      state = municipality_context[:state]
      municipality_name = municipality_context[:municipality_entry]["name"]
      content = File.read(content_file)

      # TODO: check if input is too long
      # return { error: "Content for city council members are too long" } if content.split(" ").length > @@MAX_TOKENS

      prompt = Services::Shared::GeminiPrompts
               .gemini_generate_municipal_directory_prompt(municipality_context, content, person_name)

      request_origin = "#{state}_#{municipality_name}_gemini_#{MODEL}_extract_city_people"
      response = run_prompt(prompt, request_origin,
                            response_schema: Services::Shared::ResponseSchemas::GEMINI_PEOPLE_ARRAY_SCHEMA)

      return nil if response.blank?

      # filter out invalid people
      people = response["people"].select do |person|
        Utils::NameHelper.valid_name?(person["name"])
      end

      people.map do |person|
        Services::Shared::People.format_raw_data(person, url)
      end
    end

    def run_prompt(prompt, request_origin, response_schema: nil, with_search: false)
      retry_attempts = 0
      url = "#{BASE_URI}/v1beta/models/#{MODEL}:generateContent?key=#{@api_key}"

      payload = {
        contents: [{
          parts: [{
            text: prompt
          }]
        }],
        generationConfig: {
          temperature: 0
        }
      }

      if with_search
        payload[:tools] = { googleSearch: {} }
      else
        payload[:generationConfig][:responseMimeType] = "application/json"
        payload[:generationConfig][:responseSchema] = response_schema
      end

      options = {
        body: payload.to_json,
        headers: {
          "Content-Type" => "application/json"
        },
        timeout: 180
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
        end

        puts "Failed to parse JSON response from Gemini: #{json_output}" if parsed_response.nil?

        parsed_response
      else
        puts "Request failed. HTTP Status: #{response.code}"
        puts "Response: #{response.message}"
        nil
      end
    rescue Net::ReadTimeout => e
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

    def self.get_cost(input_tokens_num, output_tokens_num)
      input_cost_per_million = 0.15 # USD
      output_cost_per_million = 0.60 # USD

      input_millions = input_tokens_num / 1_000_000.0
      output_millions = output_tokens_num / 1_000_000.0

      input_cost = input_millions * input_cost_per_million
      output_cost = output_millions * output_cost_per_million

      input_cost + output_cost
    end
  end
end
