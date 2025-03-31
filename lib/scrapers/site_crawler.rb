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
      puts "Processing links for #{url}"
      url_text_pairs = []

      begin
        response = fetch_html(url, session)
        document = Nokogiri::HTML(response)
        page_base_url = document.css("base").first&.attr("href") || url
        link_base_url = URI.parse(page_base_url).absolute? ? page_base_url : URI.join(base_domain, page_base_url)

        document.css("a").each do |link|
          href = link["href"]&.strip
          next unless valid_link?(href, base_domain)

          full_url = get_full_url(href, link_base_url)
          link_text = link.text.strip

          text_match = keywords.any? do |keyword|
            match = link_text.downcase.include?(keyword.downcase)
            match
          end

          url_match = keywords.any? do |keyword|
            match = full_url.downcase.include?(keyword.downcase)
            match
          end

          url_text_pairs << [full_url, link_text] if text_match || url_match
        end

      rescue StandardError
        []
      end

      url_text_pairs
    end

    def self.crawl(base_url, keywords, visited = {}, session = nil, max_links = 20)
      root_url ||= base_url
      links_processed = 0
      url_text_pairs = []

      # [url, text, depth]
      queue = [[base_url, "", 0]]
      current_depth = 0

      begin
        while !queue.empty? && links_processed < max_links
          # Process all links at current depth before moving deeper
          current_level_size = queue.count { |_, _, depth| depth == current_depth }

          while current_level_size.positive? && links_processed < max_links
            current_url, _, depth = queue.shift
            next if visited[current_url]

            visited[current_url] = true
            links_processed += 1
            current_level_size -= 1

            begin
              new_links = process_links(current_url, keywords, base_url, session)
              url_text_pairs.concat(new_links)

              # Add new links with increased depth
              new_links.each do |url, text|
                next if visited[url]

                queue << [url, text, depth + 1]
              end

            rescue StandardError
              []
            end
          end

          # Move to next depth level if we've processed all current level links
          current_depth += 1 if current_level_size.zero?
        end
      rescue StandardError
        []
      end

      url_text_pairs
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

    def self.valid_link?(href, base_domain)
      return false if href.nil? || href.empty?
      return false if href.starts_with?("mailto:")
      return false if href.ends_with?(".xml", ".json", ".csv", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")
      return false unless href.ascii_only?
      return false unless href.start_with?("/") || href.start_with?(base_domain)
      true
    end

    def self.get_full_url(href, link_base_url)
      href = URI::DEFAULT_PARSER.escape(href)
      href = Scrapers::Common.format_url(href)
      full_url = URI.parse(href).absolute? ? URI.parse(href).to_s : URI.join(link_base_url, href).to_s
      full_url
    end
  end
end
