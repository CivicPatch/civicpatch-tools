# frozen_string_literal: true

module Core
  class CacheManager
    def self.clean(state, geoid, source_urls)
      urls_to_keep = source_urls.map { |source| Utils::UrlHelper.url_to_safe_folder_name(source) }

      cache_dir = Core::PathHelper.get_city_cache_path(state, geoid)
      return unless Dir.exist?(cache_dir)

      cache_folders = Pathname.new(cache_dir).children.select(&:directory?).collect(&:to_s)

      cache_folders.each do |cache_folder|
        if urls_to_keep.any? { |url| cache_folder.include?(url) }
          # Remove everything except the markdown file
          files_to_remove = Dir.glob(File.join(cache_folder, "*")).reject { |file| file.end_with?(".md") }

          FileUtils.rm_rf(files_to_remove)
          next
        end

        FileUtils.rm_rf(cache_folder)
      end
    end
  end
end
