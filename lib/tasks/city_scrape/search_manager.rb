module CityScrape
  class SearchManager
    def fetch_search_results(engine, state, city_entry, existing_urls)
      new_results = get_candidate_city_directory_urls(engine, state, city_entry)

      # Get unique results
      new_results = new_results.reject { |url| existing_urls.include?(url) }

      puts "Search engine #{engine} found #{new_results.count} new urls"
      puts new_results.join("\n")

      new_results
    end

    def get_candidate_city_directory_urls(engine, state, city_entry)
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
