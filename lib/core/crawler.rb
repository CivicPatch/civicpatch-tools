# frozen_string_literal: true

# Given a base url and keyword groups, crawl the domain
require "selenium-webdriver"
require_relative "browser"

class Crawler
  MAX_PAGES = 30
  IGNORE_SUFFIXES = %w[xml pdf].freeze

  def self.crawl(base_url, max_pages: MAX_PAGES, keyword_groups: [], max_depth: 2)
    visited = Set.new
    queue = [{ url: base_url, depth: 0 }]

    results = process_queue(base_url, queue, visited, max_pages, keyword_groups, max_depth)

    results.transform_values(&:flatten).values.flatten.uniq # Ensure no duplicates
  end

  def self.process_queue(base_url, queue, visited, max_pages, keyword_groups, max_depth)
    results = Hash.new { |hash, key| hash[key] = [] } # Default to an empty array for each keyword group

    while queue.any? && visited.size < max_pages
      current = queue.shift
      next if visited.include?(current[:url])

      visited.add(current[:url])
      puts "Crawling: #{current[:url]} (#{visited.size}/#{max_pages})"

      keyword_groups.each do |keyword_group|
        found_links = follow_links(
          base_url,
          visited,
          current[:url],
          keyword_group[:keywords],
          max_depth,
          current[:depth] + 1
        )

        # Stop adding links if max_pages is reached
        remaining_slots = max_pages - visited.size
        found_links = found_links.first(remaining_slots) if remaining_slots < found_links.size

        results[keyword_group[:name]].concat(found_links) unless found_links.empty?

        # Add new links to queue only if max_pages isn't exceeded
        queue.concat(found_links.map { |url| { url: url, depth: current[:depth] + 1 } }) if visited.size < max_pages
      end
    end

    results # Return URLs grouped by keyword group name
  end

  def self.follow_links(base_url, visited, url, keywords, max_depth, depth)
    return [] if depth > max_depth

    page = fetch_page(url)
    return [] unless page

    links = extract_links(base_url, page)

    valid_links = links.select do |link|
      next false if IGNORE_SUFFIXES.any? { |suffix| link[:href].end_with?(suffix) }

      text_match?(link[:text], keywords) ||
        url_match?(link[:href], keywords)
    end

    valid_links.map { |link| absolute_url(url, link[:href]) }.reject { |link| visited.include?(link) }
  end

  def self.fetch_page(url)
    uri = URI(url)
    response = HTTParty.get(uri)
    Nokogiri::HTML(response.body)
  rescue StandardError
    puts "Failed to fetch #{url}: #{response.code}, retrying in browser"
    Browser.fetch_page(url)
  end

  def self.extract_links(base_url, page)
    # Page's base url can be rewritten, depending on the html
    page_base_url = get_page_base_url(base_url, page)
    raw_links = page.css("a").map do |link|
      href = link["href"]&.strip
      next nil unless href.present?

      full_url = get_full_url(page_base_url, href)
      next nil unless full_url

      { text: link.text.strip, href: full_url }
    end.compact

    raw_links.select do |raw_link|
      raw_link[:href].present? &&
        same_domain?(base_url, raw_link[:href])
    end
  end

  def self.get_full_url(base_url, href)
    if Addressable::URI.parse(href).absolute?
      Addressable::URI.parse(href).to_s
    else
      Addressable::URI.parse(base_url).join(href).to_s
    end
  rescue StandardError
    # Href might not be valid. Bail
    nil
  end

  def self.get_page_base_url(base_url, page)
    base_override = page.css("base").first&.attr("href")

    if base_override.present?
      Addressable::URI.parse(base_url).join(base_url)
    else
      base_url
    end
  end

  def self.absolute_url(base_url, href)
    return href if href.start_with?("http")

    URI.join(base_url, href).to_s
  end

  def self.same_domain?(base_url, href)
    base_domain = Addressable::URI.parse(base_url).host
    link_domain = Addressable::URI.parse(href).host
    base_domain == link_domain
  end

  def self.text_match?(text, keywords)
    keywords.any? do |kw|
      text.downcase.include?(kw.downcase)
    end
  end

  def self.url_match?(href, keywords)
    normalized_url = normalize_text(href)
    keywords.any? { |kw| normalized_url.include?(normalize_text(kw, remove_spaces: true)) }
  end

  def self.normalize_text(text, remove_spaces: false)
    text = text.downcase.gsub(/[^a-z0-9\s]/, "") # Remove non-alphanumeric except spaces
    text.gsub!(/\s+/, "") if remove_spaces # Remove spaces if specified
    text
  end
end
