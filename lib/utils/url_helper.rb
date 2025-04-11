module Utils
  class UrlHelper
    def self.url_to_safe_folder_name(url)
      url.gsub(/[^0-9A-Za-z.-]/, "_").gsub(/_+/, "_").gsub(/^_+|_+$/, "")
    end
  end
end
