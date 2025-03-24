module Scrapers
  module Common
    def self.sort_url_pairs(url_pairs, keyword_groups)
      grouped_urls = Hash.new { |hash, key| hash[key] = [] }

      url_pairs.each do |url, text|
        keyword_groups.each do |group_name, keywords|
          if keywords.any? { |keyword| text.downcase.include?(keyword.downcase) }
            grouped_urls[group_name] << [url, text]
          end
        end
      end

      # Rank each url_pair by text, then by keywords in the url, and finally by url length
      grouped_urls.each do |group_name, pairs|
        grouped_urls[group_name] = pairs.sort_by do |url, text|
          [
            -score_text(text, keyword_groups[group_name]), # Rank by text score
            -keyword_count_in_url(url, keyword_groups[group_name]), # Rank by keyword count in URL
            url.length # Rank by URL length (shorter is better)
          ]
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

      interlaced_results.map { |url, _text| format_url(url) }.uniq
    end

    def self.format_url(url)
      url.gsub(" ", "%20")
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

    def self.keyword_count_in_url(url, keywords)
      keywords.count { |keyword| url.downcase.include?(keyword.downcase.gsub(/[-_]/, "")) }
    end

    def self.urls_without_segments(urls, segments)
      urls.select do |url|
        url_segments = url.split("/").map(&:downcase)
        url_segments.none? { |segment| segments.include?(segment) }
      end
    end
  end
end
