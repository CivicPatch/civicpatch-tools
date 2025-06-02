# frozen_string_literal: true

module Services
  module GoogleGemini
    class ResponseSchemas
      LLM_DATA_POINT_SCHEMA = {
        type: :object,
        properties: {
          data: { type: :string },
          llm_confidence: { type: :number },
          llm_confidence_reason: { type: :string }
        }
      }.freeze
      GEMINI_PERSON_SCHEMA = {
        type: :object,
        properties: {
          name: { type: :string },
          roles: { type: :array, items: LLM_DATA_POINT_SCHEMA },
          divisions: { type: :array, items: LLM_DATA_POINT_SCHEMA },
          phone_number: LLM_DATA_POINT_SCHEMA,
          email: LLM_DATA_POINT_SCHEMA,
          website: LLM_DATA_POINT_SCHEMA,
          start_date: LLM_DATA_POINT_SCHEMA,
          end_date: LLM_DATA_POINT_SCHEMA
        },
        required: ["name"] # Enforce that name is required
      }.freeze

      GEMINI_PEOPLE_ARRAY_SCHEMA = {
        type: :object,
        properties: {
          people: { type: :array, items: GEMINI_PERSON_SCHEMA }
        },
        required: ["people"]
      }.freeze
    end
  end
end
