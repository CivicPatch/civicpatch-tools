# frozen_string_literal: true

require "openai"
require "services/shared/response_schemas"
require "utils/costs_helper"
require "utils/name_helper"
require "core/city_manager"
require "utils/retry_helper"
require "services/shared/people"

# TODO: track token usage
module Services
  class Openai
    MODEL = "gpt-4.1-mini"
    TOKEN_LIMIT = 400_000

    def initialize
      @client = OpenAI::Client.new(access_token: ENV["OPENAI_TOKEN"])
    end

    def extract_city_people(municipality_context, content_file, page_url, people_hint = [], person_name = "")
      state = municipality_context[:state]
      municipality_entry = municipality_context[:municipality_entry]

      system_instructions,
      user_instructions = Services::Prompts::OpenaiPrompts
                          .municipality_officials(municipality_context, content_file, page_url,
                                                  people_hint, person_name)

      messages = [
        { role: "system", content: system_instructions },
        { role: "user", content: user_instructions }
      ]
      response = run_prompt(messages, state, municipality_entry["name"])

      return nil if response.blank?

      response["people"].map do |person|
        Services::Shared::People.to_person(person, page_url)
      end
    end

    private

    def run_prompt(messages, state, municipality_name)
      Utils::RetryHelper.with_retry(MAX_RETRIES) do
        response = @client.chat(
          parameters: {
            model: MODEL,
            messages: messages,
            temperature: 0.0,
            response_format: { type: "json_object" }
          }
        )

        input_tokens_num = response.dig("usage", "prompt_tokens")
        output_tokens_num = response.dig("usage", "completion_tokens")
        Utils::CostsHelper.log_llm_cost(state, municipality_name, "openai", input_tokens_num, output_tokens_num, MODEL)

        json_output = response.dig("choices", 0, "message", "content")

        JSON.parse(json_output)
      end
    end

    def council_member_position?(position, position_misc)
      position.blank? && keywords_present?(position_misc)
    end

    def keywords_present?(position_misc)
      keywords = %w[position seat district ward]
      keywords.any? { |keyword| position_misc.include?(keyword) }
    end
  end
end
