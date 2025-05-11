# frozen_string_literal: true

module Core
  class CacheManager
    def self.clean(state, gnis, urls_to_keep)
      cache_dir = PathHelper.get_city_cache_path(state, gnis)
      return unless Dir.exist?(cache_dir)

      cache_folders = Pathname.new(cache_dir).children.select(&:directory?).collect(&:to_s)

      cache_folders.each do |cache_folder|
        unless urls_to_keep.any? { |url| cache_folder.include?(url) }
          puts "Removing #{cache_folder} from cache"
          FileUtils.rm_rf(cache_folder)
        end
      end
    end
  end
end
