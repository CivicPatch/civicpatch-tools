require "nokogiri"
require "httparty"

module Scrapers
  class SiteCrawler
    def self.get_urls(base_url, keywords)
      base_domain = URI(base_url).host  # Extract the base domain

    sitemap_url = find_sitemap(base_url)
    url_text_pairs = if sitemap_url
                       process_links(sitemap_url, keywords, base_domain)
    else
                       crawl(base_url, keywords, {}, base_domain)
    end

    # Sort URLs by their score based on link text
    results = url_text_pairs.sort_by { |url, text| -score_text(text, keywords) }

    results.map { |url, text| format_url(url) }.uniq
  end

  private

  def self.format_url(url)
    url.gsub(" ", "%20")
  end

  def self.find_sitemap(base_url)
    begin
      response = HTTParty.get(base_url)
      document = Nokogiri::HTML(response.body)
    rescue
      return nil
    end

    document.css("a").each do |link|
      if link.text.downcase.include?("sitemap")
        href = link["href"]&.strip  # Trim whitespace from href
        return URI.join(base_url, href).to_s if href
      end
    end
    nil
  end

  def self.process_links(url, keywords, base_domain)
    url_text_pairs = []

    begin
      response = HTTParty.get(url)
      document = Nokogiri::HTML(response.body)
    rescue => e
      puts "Error processing links: #{e}"
      return url_text_pairs
    end

    document.css("a").each do |link|
      href = link["href"]&.strip  # Trim whitespace from href
      next unless href

      # Encode the URL to ensure it is ASCII only
      href = URI::DEFAULT_PARSER.escape(href)
      href = format_url(href)

      full_url = URI.join(url, href).to_s
      next unless URI(full_url).host == base_domain  # Ensure the link belongs to the base domain

      link_text = link.text.strip
      url_text_pairs << [ full_url, link_text ] if keywords.any? { |keyword| link_text.downcase.include?(keyword.downcase) }
    end

    url_text_pairs
  end

  def self.crawl(url, keywords, visited, base_domain)
    return [] if visited[url]
    visited[url] = true  # Mark as visited before recursive call

    url_text_pairs = process_links(url, keywords, base_domain)

    # filter out links that are already visited
    url_text_pairs = url_text_pairs.reject { |full_url, _| visited[full_url] }

    # Collect URLs from the current level and recursively from deeper levels
    url_text_pairs + url_text_pairs.each_with_object([]) do |(full_url, _), all_links|
      all_links.concat(crawl(full_url, keywords, visited, base_domain))
    end
  end

  def self.score_text(text, keywords)
    score = 0
    keywords.each_with_index do |keyword, index|
      if text.downcase.include?(keyword.downcase)
          # Multiply by (keywords.size - index) to prioritize earlier keywords
          score += (keywords.size - index) * (keywords.size - index)
      end
      end
      score
    end
  end
end
