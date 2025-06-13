# frozen_string_literal: true

require "test_helper"
require "core/crawler"
require "core/browser"
require "utils/array_helper"

module Core
  class CrawlerTest < Minitest::Test
    def setup
      # A common base URL for all tests.
      @base_url = "https://www.example.com"
    end

    def test_crawl_with_multiple_keyword_groups
      council_url = "#{@base_url}/council"
      mayor_url = "#{@base_url}/mayor"
      html_map = {
        @base_url => "<html><body><a href='#{council_url}'>City Council</a><a href='#{mayor_url}'>The Mayor</a></body></html>",
        council_url => "<html><body>Council content</body></html>",
        mayor_url => "<html><body>Mayor content</body></html>"
      }
      keyword_groups = [
        { name: "council", keywords: ["council"] },
        { name: "mayor", keywords: ["mayor"] }
      ]
      fetcher_proc = ->(url) { html_map[url] || "" }
      interleaver_proc = ->(arrays) { arrays } # Intercept results before flattening

      results = nil
      Core::Browser.stub(:fetch_page_content, fetcher_proc) do
        Utils::ArrayHelper.stub(:interleave_arrays, interleaver_proc) do
          results = Core::Crawler.crawl(@base_url, keyword_groups: keyword_groups)
        end
      end

      sorted_results = results.map(&:sort).sort
      expected = [
        [council_url],
        [mayor_url]
      ]
      assert_equal expected, sorted_results, "Crawler should return correctly grouped links without cross-contamination"
    end

    def test_crawl_stops_at_max_depth
      council_url = "#{@base_url}/council"
      deep_link_url = "#{@base_url}/deep"
      html_map = {
        @base_url => "<html><body><a href='#{council_url}'>Council</a></body></html>",
        council_url => "<html><body><a href='#{deep_link_url}'>Deep Link</a></body></html>",
        deep_link_url => "<html><body>Deep Content</body></html>"
      }
      keyword_groups = [{ name: "links", keywords: ["council", "deep"] }]
      fetcher_proc = ->(url) { html_map[url] || "" }

      Core::Browser.stub(:fetch_page_content, fetcher_proc) do
        # With max_depth: 0, it should only find the council link but not visit it.
        results_depth_0 = Core::Crawler.crawl(@base_url, keyword_groups: keyword_groups, max_depth: 0)
        assert_equal [council_url], results_depth_0, "Should only find first-level links at max_depth: 0"

        # With max_depth: 1, it should find the council link, visit it, and find the deep link.
        results_depth_1 = Core::Crawler.crawl(@base_url, keyword_groups: keyword_groups, max_depth: 1)
        assert_includes results_depth_1, council_url, "Should include first-level link at max_depth: 1"
        assert_includes results_depth_1, deep_link_url, "Should include second-level link at max_depth: 1"
      end
    end

    def test_crawl_avoids_keywords
      council_url = "#{@base_url}/council-meetings"
      mayor_url = "#{@base_url}/mayor-archive"
      html_map = {
        @base_url => "<html><body><a href='#{council_url}'>Council</a><a href='#{mayor_url}'>Mayor</a></body></html>"
      }
      keyword_groups = [
        { name: "council", keywords: ["council"] },
        { name: "mayor", keywords: ["mayor"] }
      ]
      fetcher_proc = ->(url) { html_map[url] || "" }

      Core::Browser.stub(:fetch_page_content, fetcher_proc) do
        results = Core::Crawler.crawl(@base_url, keyword_groups: keyword_groups, avoid_keywords: ["meetings", "archive"])
        assert_empty results, "Should not return links containing avoid_keywords"
      end
    end

    def test_crawl_handles_no_links_found
      other_url = "#{@base_url}/other"
      html_map = { @base_url => "<html><body><a href='#{other_url}'>Other Page</a></body></html>" }
      keyword_groups = [{ name: "council", keywords: ["council"] }]
      fetcher_proc = ->(url) { html_map[url] || "" }

      Core::Browser.stub(:fetch_page_content, fetcher_proc) do
        results = Core::Crawler.crawl(@base_url, keyword_groups: keyword_groups)
        assert_empty results, "Should return an empty array when no matching links are found"
      end
    end

    def test_crawl_respects_max_pages_limit
      num_pages = Core::Crawler::MAX_PAGES + 5
      urls = (0...num_pages).map { |i| "#{@base_url}/page_#{i}" }
      page_map = {}
      urls.each_with_index do |url, i|
        next_url = (i + 1 < urls.length) ? urls[i + 1] : ""
        next_link = next_url.empty? ? "" : "<a href='#{next_url}'>Next Page</a>"
        page_map[url] = "<html><body>#{next_link}</body></html>"
      end
      page_map[@base_url] = "<html><body><a href='#{urls.first}'>Next Page</a></body></html>"

      keyword_groups = [{ name: "pages", keywords: ["page"] }]
      fetch_call_count = 0
      fetcher_proc = lambda do |url|
        fetch_call_count += 1
        page_map[url] || ""
      end

      Core::Browser.stub(:fetch_page_content, fetcher_proc) do
        Core::Crawler.crawl(@base_url, keyword_groups: keyword_groups, max_depth: num_pages + 1)
      end

      assert_equal Core::Crawler::MAX_PAGES, fetch_call_count, "Crawler should stop after visiting MAX_PAGES"
    end
  end
end 
