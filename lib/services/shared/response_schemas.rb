module Services
  module Shared
    class ResponseSchemas
      GEMINI_PERSON_SCHEMA = {
        type: :object,
        properties: {
          name: { type: :string },
          positions: { type: :array, items: { type: :string } },
          phone_number: { type: :string },
          email: { type: :string },
          website: { type: :string },
          term_date: { type: :string }
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
