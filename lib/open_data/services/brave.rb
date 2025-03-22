# frozen_string_literal: true

module Services
  class Brave
    def self.get_search_result_urls(query, with_site = "", discard_urls_with_partial = [])
      formatted_query = URI.encode_www_form_component(query)
      formatted_query = "#{formatted_query} site:#{with_site}" if with_site.present?

      if discard_urls_with_partial.present?
        formatted_query = "#{formatted_query} -#{discard_urls_with_partial.join(" -")}"
      end

      results = HTTParty.get(
        "https://api.search.brave.com/res/v1/web/search?q=#{formatted_query}",
        headers: {
          "Accept" => "application/json",
          "Accept-Encoding" => "gzip",
          "X-Subscription-Token" => Rails.application.credentials.brave_token
        }
      )
      results_content = JSON.parse(results.body)

      results_content["web"]["results"].map { |result| format_url(result["url"]) }
    end

    # fix other areas of code that use URI.parse on URL with spaces
    def self.format_url(url)
      url.gsub(" ", "%20")
    end
  end
end
