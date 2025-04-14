module Services
  module Shared
    class ResponseSchemas
      LLM_CONTACT_DATA_POINT = {
        type: :object,
        properties: {
          data: { type: :string },
          llm_confidence: { type: :number },
          llm_confidence_reason: { type: :number },
          proximity_to_name: { type: :number },
          markdown_formatting: {
            type: :object,
            properties: {
              in_list: { type: :boolean }
            }
          }
        }
      }.freeze

      GEMINI_PERSON_SCHEMA = {
        type: :object,
        properties: {
          name: { type: :string },
          phone_number: {
            type: :object,
            properties: LLM_CONTACT_DATA_POINT
          },
          emails: { type: :object, properties: LLM_CONTACT_DATA_POINT },
          websites: { type: :object, properties: LLM_CONTACT_DATA_POINT },
          positions: {
            type: :object,
            properties: LLM_CONTACT_DATA_POINT
          },
          term_dates: {
            type: :object,
            properties: LLM_CONTACT_DATA_POINT
          }
        },
        required: ["name"] # Enforce that name is required
      }.freeze

      GEMINI_PEOPLE_ARRAY_SCHEMA = {
        type: :array,
        items: GEMINI_PERSON_SCHEMA # Each item in the array should follow PERSON_SCHEMA
      }.freeze
    end
  end
end
