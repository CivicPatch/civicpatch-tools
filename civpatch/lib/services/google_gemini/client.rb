# frozen_string_literal: true

require "core/city_manager"
require "utils/costs_helper"
require "utils/name_helper"
require "httparty"
require_relative "../prompts/google_gemini_prompts"
require_relative "../shared/requests"
require_relative "../shared/people"
require_relative "response_schemas"

module Services
  module GoogleGemini
    class Client
      MODELS = %w[
        gemini-2.5-flash-preview-04-17
        gemini-2.0-flash
      ].freeze

      BASE_URI = "https://generativelanguage.googleapis.com"
      DEFAULT_TIMEOUT = 180

      def initialize
        @api_key = ENV["GOOGLE_GEMINI_TOKEN"]
      end

      def research_municipality(municipality_context)
        state = municipality_context[:state]
        municipality_entry = municipality_context[:municipality_entry]

        prompt = Services::Prompts::GoogleGeminiPrompts
                 .research_municipality(state, municipality_entry)

        response = run_prompt(
          prompt: prompt,
          state: state,
          municipality_name: municipality_entry["name"],
          with_search: true
        )

        return nil if response.blank?

        response
      end

      def extract_city_people(municipality_context, content_file, url, people_hint = [], person_name = "")
        state = municipality_context[:state]
        municipality_name = municipality_context[:municipality_entry]["name"]
        content = File.read(content_file)

        prompt = Services::Prompts::GoogleGeminiPrompts
                 .municipality_officials(municipality_context, content, people_hint, person_name)

        response = run_prompt(
          prompt: prompt,
          state: state,
          municipality_name: municipality_name,
          response_schema: Services::GoogleGemini::ResponseSchemas::GEMINI_PEOPLE_ARRAY_SCHEMA
        )

        return nil if response.blank?

        # filter out invalid people
        people = response["people"].select do |person|
          Utils::NameHelper.valid_name?(person["name"])
        end

        people.map do |person|
          Services::Shared::People.to_person(person, url)
        end
      end

      def run_prompt(request_options)
        Services::Shared::Requests.with_model_fallback(MODELS) do |model|
          make_request(model, request_options)
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

      def make_request(model, request_options)
        Services::Shared::Requests.with_progress_indicator do
          response = HTTParty.post(
            "#{BASE_URI}/v1beta/models/#{model}:generateContent?key=#{@api_key}",
            request_options(request_options)
          )

          if response.success?
            log_usage(response, model, request_options)
            parse_response(response)
          else
            log_error(response)
            nil
          end
        end
      end

      def request_options(request_options)
        {
          body: build_payload(request_options).to_json,
          headers: { "Content-Type" => "application/json" },
          timeout: DEFAULT_TIMEOUT
        }
      end

      def build_payload(request_options)
        {
          contents: [{ parts: [{ text: request_options[:prompt] }] }],
          generationConfig: {
            temperature: 0,
            responseMimeType: request_options[:with_search] ? nil : "application/json",
            responseSchema: request_options[:with_search] ? nil : request_options[:response_schema]
          },
          tools: request_options[:with_search] ? { googleSearch: {} } : nil
        }.compact
      end

      def log_usage(response, model, request_options)
        usage = response["usageMetadata"]
        Utils::CostsHelper.log_llm_cost(
          request_options[:state], request_options[:municipality_name], "google_gemini",
          usage["promptTokenCount"],
          usage["candidatesTokenCount"] + usage["thoughtsTokenCount"].to_i,
          model, with_search: request_options[:with_search]
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
end
