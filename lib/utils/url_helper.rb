module Utils
  class UrlHelper
    def self.url_to_safe_folder_name(url)
      # get rid of protocol
      url = url.gsub(%r{^https?://}, "")
      url.gsub(/[^0-9A-Za-z.-]/, "_").gsub(/_+/, "_").gsub(/^_+|_+$/, "")
    end

    def self.format_url(url)
      return nil if url.nil?

      # Parse and normalize the URL
      begin
        normalized_url = Addressable::URI.parse(url).normalize.to_s
        # Remove any trailing slashes
        normalized_url.gsub(%r{/$}, "")
      rescue StandardError => e
        puts "Error normalizing URL: #{url} - #{e.message}"
        url # Return original URL if parsing fails
      end
    end
  end
end
