module Services
  module Shared
    class GeminiPeople
      def self.format_raw_data(person)
        {
          "name" => person["name"],
          "positions" => person["positions"],
          "phone_number" => person["phone_number"],
          "email" => person["email"],
          "website" => person["website"].present? ? Utils::UrlHelper.format_url(person["website"]) : nil,
          "term_date" => person["term_date"],
          "sources" => person["sources"]
        }
      end
    end
  end
end
