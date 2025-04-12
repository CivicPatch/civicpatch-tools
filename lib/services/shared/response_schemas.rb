module Services
  module Shared
    class ResponseSchemas
      GEMINI_PERSON_SCHEMA = {
        type: :object,
        properties: {
          name: { type: :string },
          phone_number: { type: :string },
          email: { type: :string },
          website: { type: :string },
          positions: {
            type: :array,
            items: { type: :string }
          },
          start_term_date: { type: :string },
          end_term_date: { type: :string }
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
