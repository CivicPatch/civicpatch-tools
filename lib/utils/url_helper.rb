module Utils
  class UrlHelper
    def self.url_to_safe_folder_name(url)
      # get rid of protocol
      url = url.gsub(%r{^https?://}, "")
      url.gsub(/[^0-9A-Za-z.-]/, "_").gsub(/_+/, "_").gsub(/^_+|_+$/, "")
    end
  end
end
