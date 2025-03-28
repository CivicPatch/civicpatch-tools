module CityScrape
  class SearchManager
    def self.fetch_search_results(engine, state, city_entry)
      city = city_entry["name"]
      website = city_entry["website"]

      case engine
      when "manual"
        urls = Scrapers::SiteCrawler.get_urls(website, CityScrape::CityManager::KEYWORD_GROUPS)
      when "brave"
        search_query = "#{city} #{state} city council members"
        urls = Services::Brave.get_search_result_urls(search_query, website, CityScrape::CityManager::KEYWORD_GROUPS)
      end

      Scrapers::Common.urls_without_segments(urls, %w[news events event])
    end
  end
end
