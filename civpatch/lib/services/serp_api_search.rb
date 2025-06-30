# frozen_string_literal: true

module Services
  class SerpAPISearch
    ENDPOINT = "https://serpapi.com/search"

    def self.set_keys
      @api_key = ENV["SERP_API_TOKEN"]
    end

    def self.municipal_search(municipality_context, query_keywords, _or_terms_list)
      set_keys

      state = municipality_context[:state]
      municipality_entry = municipality_context[:municipality_entry]
      website = municipality_entry["website"]
      query = "#{municipality_entry["name"]} #{state} #{query_keywords} site:#{website}"
      params = {
        engine: "google",
        q: query,
        api_key: @api_key,
      }

      response = HTTParty.get(ENDPOINT, query: params)
      raise StandardError, response.message unless response.success?

      parsed_response = JSON.parse(response.body)
      parsed_response["organic_results"].map { |item| item["link"] }
    end
  end
end
