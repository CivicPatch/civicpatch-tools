# frozen_string_literal: true

require "utils/url_helper"
require_relative "crawler"

module Core
  class SearchRouter
    def self.fetch_search_results(engine, municipality_context)
      municipality_entry = municipality_context[:municipality_entry]
      government_type = municipality_context[:government_type]
      website = municipality_entry["website"]
      urls = []
      keyword_groups = Core::CityManager.get_search_keywords_as_array(government_type)

      avoid_keywords = %w[alerts news event calendar]

      puts "SearchRouter: #{engine}"

      case engine
      when "manual"
        # TODO: replace with actual keyword groups
        crawl_urls = Core::Crawler
                     .crawl(website, keyword_groups: keyword_groups, avoid_keywords: avoid_keywords)

        urls += crawl_urls
      when "brave"
        keyword_groups.map do |group|
          search_query = "#{municipality_entry["name"]} #{municipality_context[:state]} #{group[:name]}"
          urls += Services::Brave.get_search_result_urls(search_query, website)
        end
      end

      filtered_urls = Utils::UrlHelper.urls_without_keywords(urls, %w[archive alerts news event calendar video])
      filtered_urls = Utils::UrlHelper.urls_without_dates(filtered_urls)
      puts "#{engine} - urls fetched: #{urls.count}"
      pp urls
      filtered_urls.map { |url, _text| url }
    end
  end
end
