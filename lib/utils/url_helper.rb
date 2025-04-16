require 'addressable/uri'
require 'uri'

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

        uri.path = Addressable::URI.unencode_component(uri.path) if uri.path
        normalized = uri.normalize.to_s
        # Remove any trailing slashes for consistency
        normalized.gsub(%r{/$}, "")
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
        uri.host = uri.host.gsub(/^www\./, '') if uri.host
        uri.normalize.to_s.gsub(%r{/$}, "") # Keep existing normalization and trailing slash removal
      rescue StandardError => e
        puts "Error normalizing URL for comparison: #{url} - #{e.message}"
        url # Return original on error
      end
    end
  end
end
