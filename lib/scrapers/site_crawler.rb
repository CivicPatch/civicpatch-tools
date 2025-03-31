# frozen_string_literal: true

require "nokogiri"
require "httparty"
require "markitdown"
require_relative "../scrapers/common"
require_relative "../tasks/city_scrape/city_manager"

module Scrapers
  class SiteCrawler
    MAX_LINKS = 50
    TIMEOUT_SECONDS = 300
    RETRY_ATTEMPTS = 2
    FETCH_DELAY_SECONDS = 2
    FILE_EXTENSIONS_TO_SKIP = %w[.xml .json .csv .pdf .doc .docx .xls .xlsx .ppt .pptx]

    # Main entry point
    def self.get_urls(base_url, keyword_groups)
      all_keywords = keyword_groups.values.flatten

      session = initialize_browser_session
      results = crawl_site(base_url, all_keywords, session)
      session.quit if session

      url_pairs = results.map { |result| [result[:url], result[:text]] }

      Scrapers::Common.sort_url_pairs(url_pairs, keyword_groups)
    end

    # Browser handling
    def self.initialize_browser_session
      configure_browser
      Capybara::Session.new(:selenium_chrome)
    rescue StandardError => e
      puts "Browser initialization failed: #{e.message}"
      nil
    end

    def self.configure_browser
      Capybara.register_driver :selenium_chrome do |app|
        options = Selenium::WebDriver::Chrome::Options.new
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--headless") unless ENV["SHOW_BROWSER"]
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

        Capybara::Selenium::Driver.new(app, browser: :chrome, options: options)
      end
    end

    # HTML Fetching
    def self.fetch_html(url, session)
      fetch_with_client(url)
    rescue StandardError => e
      puts "HTTParty fetch failed: #{e.message}. Trying browser..."
      return fetch_with_browser(url, session) if session

      raise e
    end

    def self.fetch_with_client(url)
      response = HTTParty.get(url, timeout: 15)
      raise "HTTP Error: #{response.code}" unless response.code == 200

      response.body
    end

    def self.fetch_with_browser(url, session)
      attempts = RETRY_ATTEMPTS
      begin
        puts "Visiting #{url} with browser"
        session.visit(url)
        sleep FETCH_DELAY_SECONDS
        session.html
      rescue StandardError => e
        attempts -= 1
        raise e unless attempts > 0

        puts "Retrying browser fetch (#{attempts} attempts left)"
        sleep 1
        retry
      end
    end

    # Link processing
    def self.process_links(url, keywords, base_domain, session)
      puts "Finding links on: #{url}"
      matching_links = []

      begin
        html = fetch_html(url, session)
        document = Nokogiri::HTML(html)
        base_url = get_base_url(document, url, base_domain)

        matching_links = find_and_filter_links(document, keywords, base_url)
      rescue StandardError => e
        puts "Error processing links on #{url}: #{e.message}"
        puts "Error: #{e.backtrace.join("\n")}"
      end

      puts "Found #{matching_links.size} matching links"
      matching_links
    end

    def self.get_base_url(document, current_url, base_domain)
      page_base_url = document.css("base").first&.attr("href") || current_url
      URI.parse(page_base_url).absolute? ? page_base_url : URI.join(base_domain, page_base_url).to_s
    end

    def self.find_and_filter_links(document, keywords, base_url)
      matching_links = []
      document.css("a").each do |link|
        href = link["href"]&.strip

        full_url = get_full_url(href, base_url)
        next unless valid_link?(full_url, base_url)

        link_text = link.text.strip

        matching_links << { url: full_url, text: link_text || "none" } if keyword_match?(full_url, link_text, keywords)
      end

      matching_links
    end

    def self.keyword_match?(url, text, keywords)
      url_words = url.split(%r{[/\-_]}).join(" ")
      text_matches = text.present? && keywords.any? { |keyword| url_words.include?(keyword) }
      url_matches = keywords.any? { |keyword| text.include?(keyword) }
      text_matches || url_matches
    end

    # URL utilities
    def self.valid_link?(url, base_domain)
      return false if url.start_with?("mailto:")
      return false if FILE_EXTENSIONS_TO_SKIP.any? { |ext| url.end_with?(ext) }
      return false unless url.ascii_only?
      return false unless url.start_with?("/") || url.start_with?(base_domain)

      true
    end

    def self.get_full_url(href, base_url)
      href = URI::DEFAULT_PARSER.escape(href)
      href = Scrapers::Common.format_url(href)
      URI.parse(href).absolute? ? URI.parse(href).to_s : URI.join(base_url, href).to_s
    end

    # Main crawling logic
    def self.crawl_site(base_url, keywords, session, max_links = MAX_LINKS)
      puts "Starting crawl from: #{base_url}"
      start_time = Time.now

      visited = {}
      links_processed = 0
      matching_links = []
      queue = [{ url: base_url, text: "main page" }]

      while !queue.empty? && links_processed < max_links
        log_crawl_progress(queue, links_processed, max_links, start_time)

        current = queue.shift
        next if skip_url?(current[:url], visited)

        visited[current[:url]] = true
        puts "Processing: #{current[:url]}"

        begin
          new_links = process_links(current[:url], keywords, base_url, session)
          matching_links.concat(new_links)
          links_processed += 1

          queue_new_links(queue, new_links, visited)
        rescue StandardError => e
          handle_crawl_error(e, current[:url])
          links_processed += 1
        end

        break if timeout_reached?(start_time)
      end

      log_crawl_results(links_processed, matching_links, start_time)
      matching_links
    end

    def self.skip_url?(url, visited)
      if url.nil? || url.empty?
        puts "Skipping empty URL"
        return true
      end

      if visited[url]
        puts "Skipping already visited URL: #{url}"
        return true
      end

      false
    end

    def self.queue_new_links(queue, new_links, visited)
      unvisited_links = new_links.reject { |link| visited[link[:url]] }
      queue.concat(unvisited_links)
      puts "Added #{unvisited_links.size} links to the queue"
    end

    def self.handle_crawl_error(error, url)
      puts "Error processing #{url}: #{error.message}"
    end

    def self.timeout_reached?(start_time)
      if Time.now - start_time > TIMEOUT_SECONDS
        puts "Crawl timed out after #{TIMEOUT_SECONDS} seconds"
        return true
      end
      false
    end

    def self.log_crawl_progress(queue, links_processed, max_links, start_time)
      puts "\n--- Crawl Progress ---"
      puts "Queue size: #{queue.size}"
      puts "Links processed: #{links_processed}/#{max_links}"
      puts "Time elapsed: #{Time.now - start_time}s"
    end

    def self.log_crawl_results(links_processed, matching_links, start_time)
      puts "\n--- Crawl Complete ---"
      puts "Total time: #{Time.now - start_time}s"
      puts "Links processed: #{links_processed}"
      puts "Matching links found: #{matching_links.size}"
    end

    # Utility methods
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
        }xi # Case insensitive, ignore whitespace
      )
    end
  end
end
