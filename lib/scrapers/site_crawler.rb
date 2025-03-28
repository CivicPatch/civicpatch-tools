# frozen_string_literal: true

require "nokogiri"
require "httparty"
require "markitdown"
require_relative "../scrapers/common"
require_relative "../tasks/city_scrape/city_manager"

MAX_LINKS = 20

module Scrapers
  class SiteCrawler
    def self.get_urls(base_url, keyword_groups)
      session = Capybara::Session.new(:selenium_chrome)
      configure_browser
      # Extract all keywords from the keyword_groups hash
      all_keywords = keyword_groups.values.flatten

      url_text_pairs = crawl(base_url, all_keywords, {}, session, MAX_LINKS)
      session.quit

      Scrapers::Common.sort_url_pairs(url_text_pairs, keyword_groups)
    end

    def self.fetch_html(url, session)
      begin
        html = fetch_with_client(url)
      rescue StandardError
        html = fetch_with_browser(url, session)
      end

      html
    end

    def self.fetch_with_client(url)
      response = HTTParty.get(url)

      raise "403 Forbidden: #{url}" if response.code == 403

      response.body
    end

    def self.fetch_with_browser(url, session)
      session.visit(url)

      sleep 5
      session.html
    end

    def self.process_links(url, keywords, base_domain, session)
      url_text_pairs = []

      begin
        puts "Processing links: #{url}"
        response = fetch_html(url, session)

        document = Nokogiri::HTML(response)
        page_base_url = document.css("base").first&.attr("href") || url
        link_base_url = URI.parse(page_base_url).absolute? ? page_base_url : URI.join(base_domain, page_base_url)
      rescue StandardError => e
        puts "Error processing links: #{e}"
        puts "Backtrace: #{e.backtrace}"
        return url_text_pairs
      end

      document.css("a").each do |link|
        # ignore if the link is a mailto link
        href = link["href"]&.strip # Trim whitespace from href
        next unless href
        next if href.starts_with?("mailto:")
        next if href.ends_with?(".xml", ".json", ".csv", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")

        # Skip URLs with non-ASCII characters
        next unless href.ascii_only? # Skip if href contains non-ASCII characters

        # Encode the URL to ensure it is ASCII only
        href = URI::DEFAULT_PARSER.escape(href)
        href = Scrapers::Common.format_url(href)
        # Check if the href is an absolute URL
        full_url = URI.parse(href).absolute? ? URI.parse(href).to_s : URI.join(link_base_url, href).to_s
        next unless URI(full_url).host == URI(base_domain).host # Ensure the link belongs to the base domain

        link_text = link.text.strip
        url_text_pairs << [full_url, link_text] if keywords.any? do |keyword|
          link_text.downcase.include?(keyword.downcase)
        end
      end

      url_text_pairs
    end

    def self.crawl(base_url, keywords, visited = {}, session = nil, max_links = nil)
      root_url ||= base_url
      links_processed = 0
      grouped_urls = Hash.new { |hash, key| hash[key] = [] }
      url_text_pairs = []

      queue = [[base_url, "", {}]]  # [url, text, scores]

      while !queue.empty? && (max_links.nil? || links_processed < max_links)
        current_url, current_text, current_scores = queue.shift
        next if visited[current_url]

        visited[current_url] = true
        links_processed += 1

        begin
          new_links = process_links(current_url, keywords, base_url, session)

          # Process and rank new links
          new_links.each do |url, text|
            next if visited[url]

            scores = calculate_ranking(url, text)

            # Add to queue, maintaining priority based on scores
            insert_index = queue.bsearch_index do |_, _, other_scores|
              compare_scores(scores, other_scores).negative?
            end || queue.length
            queue.insert(insert_index, [url, text, scores])
          end

          CityScrape::CityManager::KEYWORD_GROUPS.each_key do |group_name|
            if current_scores[group_name]
              grouped_urls[group_name] << [current_url, current_text]
            end
          end
        end
      end

      # Return sorted pairs maintaining the same grouping and sorting as Common.sort_url_pairs
      grouped_urls.values.flatten(1)
    end

    # Helper method to calculate ranking score for a URL and text
    def self.calculate_ranking(url, text)
      scores = {}
      CityScrape::CityManager::KEYWORD_GROUPS.each do |group_name, keywords|
        next unless keywords.any? { |keyword| text.downcase.include?(keyword.downcase) }

        date_penalty = if has_date?(url.downcase) || has_date?(text.downcase)
          100  # Increase this number to penalize dates more heavily
        else
          0
        end

        scores[group_name] = [
          -Scrapers::Common.score_text(text, keywords),
          -Scrapers::Common.keyword_count_in_url(url, keywords),
          url.length + date_penalty  # Add penalty to length score
        ]
      end
      scores
    end

    def self.has_date?(text)
      text.match?(
        %r{
          (?:
            /                    # URL formats (must start with slash)
            (?:
              \d{4}[-_/]\d{2}[-_/]\d{2} |  # 2025/20/03, 2025_20_03
              (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-_]?\d{1,2}  # december_18, dec-18
            )
            / |                  # URL formats must end with slash
            (?:^|\s)            # Plaintext formats (must start with space or beginning of string)
            (?:
              \d{4}[-/]\d{2}[-/]\d{2} |    # 2012-03-02
              (?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}    # june 15
            )
            (?:\s|$)            # Plaintext formats must end with space or end of string
          )
        }xi                     # Case insensitive, ignore whitespace
      )
    end

    def self.configure_browser
      Capybara.register_driver :selenium_chrome do |app|
        options = Selenium::WebDriver::Chrome::Options.new
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--headless") unless ENV["SHOW_BROWSER"]
        # set user agent to headed chrome
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

        Capybara::Selenium::Driver.new(app, browser: :chrome, options: options)
      end
    end

    def self.compare_scores(scores1, scores2)
      # Compare scores using the same priority as the original algorithm
      CityScrape::CityManager::KEYWORD_GROUPS.each do |group_name, _|
        score1 = scores1[group_name]
        score2 = scores2[group_name]

        next if score1.nil? && score2.nil?
        return -1 if score1.nil?
        return 1 if score2.nil?

        comparison = score1 <=> score2
        return comparison unless comparison == 0
      end
      0
    end
  end
end
