require "nokogiri"
require "httparty"
require "markitdown"

module Scrapers
  class SiteCrawler
    def self.get_urls(base_url, keyword_groups)
      # Extract all keywords from the keyword_groups hash
      all_keywords = keyword_groups.values.flatten

      url_text_pairs = crawl(base_url, all_keywords, {}, base_url)

      # Categorize URLs by keyword groups
      grouped_urls = Hash.new { |hash, key| hash[key] = [] }

      url_text_pairs.each do |url, text|
        keyword_groups.each do |group_name, keywords|
          if keywords.any? { |keyword| text.downcase.include?(keyword.downcase) }
            grouped_urls[group_name] << [url, text]
          end
        end
      end

      # Sort URLs within each group by the specified rules
      grouped_urls.each do |group_name, urls|
        grouped_urls[group_name] = urls.sort_by do |url, text|
          keywords = keyword_groups[group_name]
          root = URI.parse(url).scheme + "://" + URI.parse(url).host
          segments_count = url.split('/').size
          contains_keyword = keywords.any? { |keyword| text.downcase.include?(keyword.downcase) } ? 0 : 1
          [root, segments_count, contains_keyword]  # Sort by root, then segments count, then keyword presence
        end
      end

      # Interlace the sorted URLs from each group
      interlaced_results = []
      max_length = grouped_urls.values.map(&:size).max

      (0...max_length).each do |i|
        grouped_urls.each_value do |urls|
          interlaced_results << urls[i] if urls[i]
        end
      end

      interlaced_results.map { |url, text| format_url(url) }.uniq
    end

  private

  def self.format_url(url)
    url.gsub(" ", "%20")
  end

  def self.process_links(url, keywords, base_domain)
    url_text_pairs = []

    begin
      response = HTTParty.get(url)
      document = Nokogiri::HTML(response.body)
      page_base_url = document.css("base").first&.attr("href") || url
      link_base_url = URI.parse(page_base_url).absolute? ? page_base_url : URI.join(base_domain, page_base_url)
    rescue => e
      puts "Error processing links: #{e}"
      puts "Backtrace: #{e.backtrace}"
      return url_text_pairs
    end

    document.css("a").each do |link|
      href = link["href"]&.strip  # Trim whitespace from href
      next unless href
      next if href.ends_with?(".xml", ".json", ".csv", ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx")

      # Encode the URL to ensure it is ASCII only
      href = URI::DEFAULT_PARSER.escape(href)
      href = format_url(href)
      # Check if the href is an absolute URL
      full_url = URI.parse(href).absolute? ? href : URI.join(link_base_url, href).to_s
      next unless URI(full_url).host == URI(base_domain).host  # Ensure the link belongs to the base domain


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
