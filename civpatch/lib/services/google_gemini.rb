# frozen_string_literal: true

require "core/city_manager"
require "utils/costs_helper"
require "utils/name_helper"
require_relative "shared/gemini_prompts"
require_relative "shared/requests"

module Services
  class GoogleGemini
    MODELS = %w[
      gemini-2.5-flash-preview-04-17
      gemini-2.0-flash
    ].freeze

    BASE_URI = "https://generativelanguage.googleapis.com"
    MAX_RETRIES = 5
    BASE_SLEEP = 5
    DEFAULT_TIMEOUT = 180

    def initialize
      @api_key = ENV["GOOGLE_GEMINI_TOKEN"]
    end

    def search_for_people(municipality_context)
      state = municipality_context[:state]
      municipality_entry = municipality_context[:municipality_entry]

      prompt = Services::Shared::GeminiPrompts
               .gemini_generate_search_for_people_prompt(state, municipality_entry)

      response = run_prompt(prompt, state, municipality_entry["name"], with_search: true)

      return nil if response.blank?

      response
    end

    def extract_city_people(municipality_context, content_file, url, people_hint = [], person_name = "")
      state = municipality_context[:state]
      municipality_name = municipality_context[:municipality_entry]["name"]
      content = File.read(content_file)

      # TODO: check if input is too long
      # return { error: "Content for city council members are too long" } if content.split(" ").length > @@MAX_TOKENS

      prompt = Services::Shared::GeminiPrompts
               .gemini_generate_municipal_directory_prompt(municipality_context, content, people_hint, person_name)

      response = run_prompt(prompt, state, municipality_name,
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

    def run_prompt(prompt, state, municipality_name, response_schema: nil, with_search: false)
      Services::Shared::Requests.with_model_fallback(MODELS) do |model|
        make_request(prompt, model, response_schema, with_search, state, municipality_name)
      end
    end

    def get_cost(input_tokens_num, output_tokens_num)
      input_cost_per_million = 0.15 # USD
      output_cost_per_million = 0.60 # USD

      input_millions = input_tokens_num / 1_000_000.0
      output_millions = output_tokens_num / 1_000_000.0

      input_millions * input_cost_per_million + output_millions * output_cost_per_million
    end

    private

    def make_request(prompt, model, response_schema, with_search, state, municipality_name)
      Services::Shared::Requests.with_progress_indicator do
        response = HTTParty.post(
          "#{BASE_URI}/v1beta/models/#{model}:generateContent?key=#{@api_key}",
          request_options(prompt, response_schema, with_search)
        )

        if response.success?
          log_usage(response, model, with_search, state, municipality_name)
          parse_response(response)
        else
          log_error(response)
          nil
        end
      end
    end

    def request_options(prompt, response_schema, with_search)
      {
        body: build_payload(prompt, response_schema, with_search).to_json,
        headers: { "Content-Type" => "application/json" },
        timeout: DEFAULT_TIMEOUT
      }
    end

    def build_payload(prompt, response_schema, with_search)
      {
        contents: [{ parts: [{ text: prompt }] }],
        generationConfig: {
          temperature: 0,
          responseMimeType: with_search ? nil : "application/json",
          responseSchema: with_search ? nil : response_schema
        },
        tools: with_search ? { googleSearch: {} } : nil
      }.compact
    end

    def log_usage(response, model, with_search, state, municipality_name)
      usage = response["usageMetadata"]
      Utils::CostsHelper.log_llm_cost(
        state, municipality_name, "google_gemini",
        usage["promptTokenCount"],
        usage["candidatesTokenCount"] + usage["thoughtsTokenCount"].to_i,
        model, with_search: with_search
      )
    end

    def log_error(response)
      puts "Request failed. HTTP Status: #{response.code}\nResponse: #{response.message}"
    end

    def parse_response(response)
      JSON.parse(response["candidates"].first["content"]["parts"].first["text"].gsub(/```json|```/, ""))
    rescue JSON::ParserError => e
      puts "Failed to parse JSON response from Gemini: #{e.message}"
      nil
    end
  end
end
