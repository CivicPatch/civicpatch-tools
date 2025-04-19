module Core
  class SearchRouter
    def self.fetch_search_results(engine, state, city_entry, government_type)
      city = city_entry["name"]
      website = city_entry["website"]
      urls = []
      keyword_groups = Core::CityManager.get_search_keywords_as_array(government_type)

      avoid_keywords = %w[alerts news event calendar]

      puts "SearchRouter: #{engine}"

      case engine
      when "manual"
        # TODO: replace with actual keyword groups
        urls += Crawler.crawl(website, keyword_groups: keyword_groups, avoid_keywords: avoid_keywords)
      when "brave"
        keyword_groups.map do |group|
          search_query = "#{city} #{state} #{group[:name]}"
          urls += Services::Brave.get_search_result_urls(search_query, website)
        end
      end

      filtered_urls = Scrapers::Common.urls_without_keywords(urls, %w[alerts news event calendar video])
      filtered_urls = Scrapers::Common.urls_without_dates(filtered_urls)
      puts "Urls fetched: urls: #{urls}"
      filtered_urls.map { |url, _text| url }
    end
  end
end
