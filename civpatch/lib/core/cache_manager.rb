# frozen_string_literal: true

module Core
  class CacheManager
    def self.clean(state, gnis, source_urls) # rubocop:disable Metrics/CyclomaticComplexity
      urls_to_keep = source_urls.map { |source| Utils::UrlHelper.url_to_safe_folder_name(source) }

      cache_dir = PathHelper.get_city_cache_path(state, gnis)
      return unless Dir.exist?(cache_dir)

      cache_folders = Pathname.new(cache_dir).children.select(&:directory?).collect(&:to_s)

      cache_folders.each do |cache_folder|
        if urls_to_keep.any? { |url| cache_folder.include?(url) }
          # Remove all but .md files
          files = Dir.glob("#{cache_folder}/*")
          files.each do |file|
            next if file.end_with?(".md")

            puts "Removing #{file} from cache"
            File.delete(file)
          end
        else
          puts "Removing #{cache_folder} from cache"
          FileUtils.rm_rf(cache_folder)
        end
      end
    end
  end
end
