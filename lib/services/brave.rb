# frozen_string_literal: true

require "utils/url_helper"

module Services
  class Brave
    def self.get_search_result_urls(query, with_site = "")
      formatted_query = URI.encode_www_form_component(query)
      formatted_query = "#{formatted_query} site:#{with_site}" if with_site.present?

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
