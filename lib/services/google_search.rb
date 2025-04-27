module Services
  class GoogleSearch
    GOOGLE_SEARCH_ENDPOINT = "https://www.googleapis.com/customsearch/v1".freeze

    def self.set_keys
      @api_key = ENV["GOOGLE_SEARCH_API_KEY"]
      @search_engine_id = ENV["GOOGLE_SEARCH_ENGINE_ID"]
    end

    def self.municipal_search(municipality_context, query_keywords)
      set_keys

      state = municipality_context[:state]
      municipality_entry = municipality_context[:municipality_entry]
      query = "#{municipality_entry["name"]} #{state} #{query_keywords}"
      website = municipality_entry["website"]
      params = {
        key: @api_key,
        cx: @search_engine_id,
        siteSearch: website,
        siteSearchFilter: "i",
        q: query
      }

      response = HTTParty.get(GOOGLE_SEARCH_ENDPOINT, query: params)
      raise StandardError, response.message unless response.success?

      parsed_response = JSON.parse(response.body)
      parsed_response["items"].map { |item| item["link"] }
    end
  end
end
