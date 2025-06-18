# frozen_string_literal: true

require "httparty"
require "json"
require_relative "../prompts/google_gemini_prompts"
require_relative "../shared/people"
require "utils/name_helper"

module Services
  module TogetherAI
    class Client
      MODELS = [
        "mistralai/Mixtral-8x22B-Instruct-v0.1"
      ].freeze

      API_URL = "https://api.together.xyz/v1/chat/completions"
      DEFAULT_TIMEOUT = 180

      def initialize
        @api_key = ENV["TOGETHERAI_TOKEN"]
        raise "TOGETHERAI_TOKEN not set" unless @api_key
      end

      def extract_city_people(municipality_context, content_file, url, people_hint = [], person_name = "")
        state = municipality_context[:state]
        municipality_name = municipality_context[:municipality_entry]["name"]
        content = File.read(content_file)

        prompt = Prompts::GoogleGeminiPrompts
                   .municipality_officials(municipality_context, content, people_hint, person_name)

        response = run_prompt(
          prompt: prompt,
          state: state,
          municipality_name: municipality_name
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
        MODELS.each do |model|
          response = make_request(model, request_options)
          return response if response.present?
        end
        nil
      end

      private

      def make_request(model, request_options)
        body = {
          model: model,
          messages: [
            { role: "user", content: request_options[:prompt] }
          ],
          max_tokens: 2048,
          temperature: 0
        }

        response = HTTParty.post(
          API_URL,
          headers: {
            "Authorization" => "Bearer #{@api_key}",
            "Content-Type" => "application/json"
          },
          body: body.to_json,
          timeout: DEFAULT_TIMEOUT
        )

        puts "TogetherAI response: #{response.code} #{response.body}" if response.code != 200

        if response.success?
          parse_response(response)
        else
          puts "TogetherAI request failed: #{response.code} #{response.body}"
          nil
        end
      end

      def parse_response(response)
        text = response["choices"]&.first&.dig("message", "content")
        return nil unless text

        # Remove markdown code block if present
        json_str = text.gsub(/```json|```/, "")
        JSON.parse(json_str)
      rescue JSON::ParserError => e
        puts "Failed to parse JSON response from TogetherAI: #{e.message}"
        nil
      end
    end
  end
end