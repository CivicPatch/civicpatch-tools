# frozen_string_literal: true

require "utils/url_helper"

module Services
  class Brave
    def self.municipal_search(municipality_context, query_keywords, _or_terms_list)
      state = municipality_context[:state]
      municipality_entry = municipality_context[:municipality_entry]
      city = municipality_entry["name"]
      formatted_query = "#{city}, #{state} #{query_keywords} site:#{municipality_entry["website"]}"
      # or terms not supported yet

      results = HTTParty.get(
        "https://api.search.brave.com/res/v1/web/search?q=#{formatted_query}",
        headers: {
          "Accept" => "application/json",
          "Accept-Encoding" => "gzip",
          "X-Subscription-Token" => ENV["BRAVE_TOKEN"]
        }
      )
      results_content = JSON.parse(results.body)

      return [] if results_content["web"].blank?

      url_text_pairs = results_content["web"]["results"].map do |result|
        {
          "url" => result["url"],
          "text" => result["title"]
        }
      end

      url_text_pairs.map { |pair| Utils::UrlHelper.format_url(pair["url"]) }
    end
  end
end
