# frozen_string_literal: true

require "nokogiri"
require "httparty"
require "markitdown"
require_relative "../scrapers/common"

MAX_LINKS = 20

module Scrapers
  class SiteCrawler
    def self.get_urls(base_url, keyword_groups)
      session = Capybara::Session.new(:selenium_chrome)
      configure_browser
      # Extract all keywords from the keyword_groups hash
      all_keywords = keyword_groups.values.flatten

      url_text_pairs = crawl(base_url, all_keywords, {}, base_url, session, MAX_LINKS)
      session.quit

      Scrapers::Common.sort_url_pairs(url_text_pairs, keyword_groups)
    end

    def self.fetch_html(url, session)
      begin
        html = fetch_with_client(url)
      rescue StandardError => e
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
        href = link["href"]&.strip # Trim whitespace from href
        next unless href
        next if href.ends_with?(".xml", ".json", ".csv", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")

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

    def self.crawl(url, keywords, visited, base_domain, session, max_links = Float::INFINITY)
      return [] if visited[url] || visited.size >= max_links

      visited[url] = true # Mark as visited before recursive call

      url_text_pairs = process_links(url, keywords, base_domain, session)

      # filter out links that are already visited
      url_text_pairs = url_text_pairs.reject { |full_url, _| visited[full_url] }

      # Collect URLs from the current level and recursively from deeper levels
      url_text_pairs + url_text_pairs.each_with_object([]) do |(full_url, _), all_links|
        break all_links if all_links.size >= max_links # Stop if max_links is reached
        all_links.concat(crawl(full_url, keywords, visited, base_domain, session, max_links))
      end
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
  end
end
