# frozen_string_literal: true

require "nokolexbor"
require "addressable/uri"
require "uri"

module Utils
  class UrlHelper
    def self.is_same?(url1, url2)
      normalize_for_comparison(url1) == normalize_for_comparison(url2)
    end

    def self.url_to_safe_folder_name(url)
      # get rid of protocol
      url = url.gsub(%r{^https?://}, "")
      url.gsub(/[^0-9A-Za-z.-]/, "_").gsub(/_+/, "_").gsub(/^_+|_+$/, "")
    end

    def self.format_url(url)
      return nil if url.nil?

      begin
        uri = Addressable::URI.parse(url)
        # Always use https
        uri.scheme = "https"

        normalized_uri = uri.normalize
        normalized_string = normalized_uri.to_s
        # Remove any trailing slashes for consistency
        normalized_string = normalized_string.gsub(%r{/$}, "")
        # Remove fragments
        normalized_string.gsub(/#.*$/, "")
      rescue StandardError => e
        puts "Error normalizing URL: #{url} - #{e.message}"
        url
      end
    end

    def self.normalize_for_comparison(url)
      return nil if url.nil?

      begin
        uri = Addressable::URI.parse(url)
        # Remove www. from the beginning of the host
        uri.host = uri.host.gsub(/^www\./, "") if uri.host
        uri.normalize.to_s.gsub(%r{/$}, "") # Keep existing normalization and trailing slash removal
      rescue StandardError => e
        puts "Error normalizing URL for comparison: #{url} - #{e.message}"
        url # Return original on error
      end
    end

    def self.format_links_to_absolute(page_html_string, page_url)
      base_url = extract_page_base_url(page_html_string, page_url)
      nokolexbor_html = Nokolexbor::HTML(page_html_string)

      nokolexbor_html.css("a, img").each do |link|
        if link.name == "a"
          href = link["href"]&.strip
          next if href.blank? || href.start_with?("mailto:", "tel:")

          link["href"] = format_url(Addressable::URI.join(base_url, href).to_s)
        elsif link.name == "img"
          src = link["src"]&.strip
          next if src.blank?

          link["src"] = format_url(Addressable::URI.join(base_url, src).to_s)
        end
      rescue StandardError
        # Error formatting link -- might be invalid
      end

      nokolexbor_html.to_html
    end

    def self.extract_page_base_url(page_html_string, default_url)
      base_elements = Nokolexbor::HTML(page_html_string).css("base")

      if base_elements.empty?
        default_url_with_slash = default_url.dup
        default_url_with_slash += "/" unless default_url_with_slash.end_with?("/")
        default_url_with_slash
      else
        base_href_attribute = base_elements[0]["href"].to_s.strip

        # Resolve the base href against the document's URL
        # This handles cases like <base href="/"> or <base href="../">
        absolute_base_url = if base_href_attribute.start_with?("http")
                              base_href_attribute
                            else
                              Addressable::URI.join(default_url, base_href_attribute).to_s
                            end

        # Ensure it ends with a slash for proper joining later
        absolute_base_url += "/" unless absolute_base_url.end_with?("/")
        absolute_base_url
      end
    end

    def self.urls_without_keywords(url_pairs, keywords)
      url_pairs.select do |url, _text|
        keywords.none? { |keyword| url.downcase.include?(keyword.downcase) }
      end
    end

    def self.urls_without_dates(url_pairs)
      url_pairs.reject do |url|
        uri = URI.parse(url)
        path = uri.path

        # Check for date patterns (YYYY/MM/DD) in the URL path
        path.match?(%r{/\d{4}/\d{2}/\d{2}/})
      end
    end
  end
end
