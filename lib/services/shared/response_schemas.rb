module Services
  module Shared
    class ResponseSchemas
      LLM_DATA_POINT_SCHEMA = {
        type: :object,
        properties: {
          data: { type: :string },
          llm_confidence: { type: :number },
          llm_confidence_reason: { type: :string },
          proximity_to_name: { type: :number },
          markdown_formatting: { type: :object, properties: { in_list: { type: :boolean } } }
        }
      }
      GEMINI_PERSON_SCHEMA = {
        type: :object,
        properties: {
          name: { type: :string },
          positions: { type: :array, items: { type: :string } },
          phone_number: LLM_DATA_POINT_SCHEMA,
          email: LLM_DATA_POINT_SCHEMA,
          website: LLM_DATA_POINT_SCHEMA,
          term_date: LLM_DATA_POINT_SCHEMA
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
