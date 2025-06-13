# frozen_string_literal: true

# Given a base url and keyword groups, crawl the domain
require "selenium-webdriver"
require "nokolexbor"
require "utils/array_helper"
require_relative "browser"
require_relative "../utils/url_helper"

module Core
  class Crawler
    MAX_PAGES = 15
    IGNORE_SUFFIXES = %w[xml pdf doc docx].freeze

    def self.crawl(base_url, max_pages: MAX_PAGES, keyword_groups: [], max_depth: 2, avoid_keywords: [])
      visited = Set.new
      queue = [{ url: base_url, depth: 0 }]

      results = process_queue(
        base_url, queue, visited, max_pages,
        keyword_groups, max_depth, avoid_keywords
      )

      # Sort by URL length, then shuffle within groups
      results_to_interleave = results.values
                                     .map { |group| group.sort_by(&:length).shuffle }

      results = Utils::ArrayHelper.interleave_arrays(results_to_interleave)
                                  &.uniq # Remove duplicates

      results || []
    end

    def self.process_queue(
      base_url, queue, visited, max_pages,
      keyword_groups, max_depth, avoid_keywords
    )
      results = Hash.new { |hash, key| hash[key] = [] }

      while queue.any? && visited.size < max_pages
        current = queue.shift
        next if visited.include?(current[:url])
        next if current[:depth] > max_depth

        visited.add(current[:url])

        results, visited, new_links = process_keyword_groups(
          base_url, visited, current, keyword_groups,
          max_depth, avoid_keywords, results
        )

        new_links.each do |link_url|
          queue.push({ url: link_url, depth: current[:depth] + 1 })
        end
      end

      results
    end

    private_class_method def self.process_keyword_groups(
      base_url, visited, current, keyword_groups,
      max_depth, avoid_keywords, results
    )
      all_new_links = []
      keyword_groups.each do |keyword_group|
        new_found_links, visited = follow_links(
          base_url, visited, current[:url],
          keyword_group[:keywords], max_depth,
          current[:depth] + 1, avoid_keywords
        )

        unless new_found_links.empty?
          results[keyword_group[:name]].concat(new_found_links)
          all_new_links.concat(new_found_links)
        end
      end

      [results, visited, all_new_links.uniq]
    end

    def self.follow_links(base_url, visited, url, keywords, max_depth, depth, avoid_keywords)
      page = fetch_page(url)
      visited.add(url)
      return [[], visited] unless page

      links = extract_links(page, base_url)

      valid_links = links.select do |link|
        next false if IGNORE_SUFFIXES.any? { |suffix| link[:href].end_with?(suffix) }
        next false if text_match?(link[:text], avoid_keywords) ||
                      url_match?(link[:href], avoid_keywords)

        text_match?(link[:text], keywords) ||
          url_match?(link[:href], keywords)
      end

      found_links = valid_links.map { |link| link[:href] }.reject { |link_href| visited.include?(link_href) }
      [found_links, visited]
    end

    def self.fetch_page(url)
      html = Core::Browser.fetch_page_content(url)
      Nokolexbor::HTML(html)
    end

    def self.extract_links(page, base_url)
      # Page's base url can be rewritten, depending on the html
      raw_links = page.css("a").map do |link|
        href = link["href"]&.strip
        next nil unless href.present?

        { text: link.text.strip, href: Utils::UrlHelper.format_url(href) }
      end.compact

      raw_links.select do |raw_link|
        raw_link[:href].present? &&
          same_domain?(base_url, raw_link[:href])
      end
    end

    def self.same_domain?(base_url, href)
      base_uri = Addressable::URI.parse(base_url)
      link_uri = Addressable::URI.parse(href)

      base_host = base_uri.host
      link_host = link_uri.host

      return false unless base_host.present? && link_host.present?

      core_base_host = base_host.start_with?("www.") ? base_host[4..] : base_host
      core_link_host = link_host.start_with?("www.") ? link_host[4..] : link_host

      core_base_host == core_link_host
    rescue StandardError
      false
    end

    def self.text_match?(text, keywords)
      keywords.any? do |kw|
        text.downcase.include?(kw.downcase)
      end
    end

    def self.url_match?(href, keywords)
      normalized_url = normalize_text(href)
      keywords.any? { |kw| normalize_text(normalized_url).include?(kw) }
    end

    def self.normalize_text(text)
      text.downcase.gsub(/[^a-z0-9\s]/, " ") # Replace non-alphanumeric with spaces
    end
  end
end
