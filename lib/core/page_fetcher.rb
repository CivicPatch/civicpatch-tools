# frozen_string_literal: true

require "capybara"
require "selenium-webdriver"
require "markitdown"
require "sanitize"
require "marcel"

require "utils/url_helper"
require_relative "../core/browser"

module Core
  class PageFetcher
    @@image_map ||= {}

    def image_map
      @@image_map
    end

    # TODO: -- robots.txt?
    def extract_content(url, destination_dir)
      cached_file = PathHelper.project_path(File.join(destination_dir.to_s, "step_3_markdown_content.md"))

      if File.exist?(cached_file)
        puts "Skipping page fetch to #{url} because cache file already exists"
        return [cached_file, image_map]
      end

      image_dir = PathHelper.project_path(File.join(destination_dir, "images"))
      html, image_map = Browser.fetch_page_and_images(url, image_dir)

      return [nil, nil] if html.blank?

      FileUtils.mkdir_p(destination_dir)

      File.write(PathHelper.project_path(File.join(destination_dir.to_s, "step_1_original_html.html")), html)

      parsed_html = with_prefixed_image_urls(html)
      parsed_html = Sanitize.fragment(parsed_html, Sanitize::Config::RELAXED)
      nokogiri_doc = Nokogiri::HTML(parsed_html)

      File.write(PathHelper.project_path(File.join(destination_dir.to_s, "step_2_parsed_html.html")),
                 parsed_html)

      markdown_content = Markitdown.from_nokogiri(nokogiri_doc)
      markdown_content_file_path = PathHelper.project_path(File.join(destination_dir.to_s,
                                                                     "step_3_markdown_content.md"))
      File.write(markdown_content_file_path, markdown_content)
      content_file_path = PathHelper.project_path(markdown_content_file_path)

      [content_file_path, image_map]
    end

    private

    # TODO: Upload images to Digital Ocean Spaces
    def with_prefixed_image_urls(html)
      doc = Nokogiri::HTML(html)
      # for all image tags, prefix the src string with images
      doc.css("img").each do |img|
        next if img["src"].blank?

        img["src"] = "images/#{img["src"]}"
      end

      doc
    end
  end
end
