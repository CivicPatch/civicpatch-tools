require "addressable/uri"
require "uri"

module Utils
  class UrlHelper
    def self.url_to_safe_folder_name(url)
      # get rid of protocol
      url = url.gsub(%r{^https?://}, "")
      url.gsub(/[^0-9A-Za-z.-]/, "_").gsub(/_+/, "_").gsub(/^_+|_+$/, "")
    end

    def self.format_url(url)
      return nil if url.nil?

      begin
        uri = Addressable::URI.parse(url)

        normalized_uri = uri.normalize
        normalized_string = normalized_uri.to_s
        # Remove any trailing slashes for consistency
        normalized_string.gsub(%r{/$}, "")
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
      nokogiri_html = Nokogiri::HTML(page_html_string)
      nokogiri_html.css("a").each do |link|
        next if link["href"].blank?

        link["href"] = link["href"].strip
        next if link["href"].start_with?("mailto:")
        next if link["href"].start_with?("tel:")

        begin
          absolute_url = Addressable::URI.join(base_url, link["href"]).to_s
          absolute_url = format_url(absolute_url)
          link["href"] = absolute_url
        rescue StandardError => e
          puts "Error formatting link: #{link["href"]} - #{e.message}"
          next
        end
      end

      nokogiri_html.to_html
    end

    # NOTE: you should not have to use this method directly
    def self.extract_page_base_url(page_html_string, default_url)
      begin
        base_elements = Nokogiri::HTML(page_html_string).css("base")

        unless base_elements.empty?
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
          return absolute_base_url
        end
      rescue StandardError => e
        puts "Error detecting/resolving base URL: #{e.message}"
      end

      # Fallback to the original document URL if no valid base tag found
      # Ensure it ends with a slash
      default_url_with_slash = default_url.dup
      default_url_with_slash += "/" unless default_url_with_slash.end_with?("/")
      default_url_with_slash
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
