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
    WAIT_TIME = 2

    def initialize
      # @image_map = {}
    end

    # TODO: -- robots.txt?
    def extract_content(url, destination_dir)
      cached_file = Core::PathHelper.project_path(File.join(destination_dir.to_s, "step_3_markdown_content.md"))

      if File.exist?(cached_file)
        puts "Skipping page fetch to #{url} because cache file already exists"
        # return [cached_file, @image_map]
        return cached_file
      end

      # image_dir = PathHelper.project_path(File.join(destination_dir, "images"))
      response = Browser.fetch_page_content(url, { # image_dir: image_dir,
                                              wait_for: WAIT_TIME,
                                              include_api_content: true
                                            })
      html = response[:page_html]

      # @image_map = @image_map.merge(response[:image_map]) if response && response[:image_map].present?

      # return [nil, nil] if html.blank?
      return nil if html.blank?

      FileUtils.mkdir_p(destination_dir)

      File.write(Core::PathHelper.project_path(File.join(destination_dir.to_s, "step_1_original_html.html")), html)

      sanitized_doc = sanitize_html(html)

      File.write(Core::PathHelper.project_path(File.join(destination_dir.to_s, "step_2_sanitized_html.html")),
                 sanitized_doc.to_html)

      markdown_content = Markitdown.from_nokogiri(sanitized_doc)
      markdown_content_file_path = Core::PathHelper.project_path(File.join(destination_dir.to_s,
                                                                           "step_3_markdown_content.md"))
      File.write(markdown_content_file_path, markdown_content)

      Core::PathHelper.project_path(markdown_content_file_path)
      # [content_file_path, @image_map]
    end

    def sanitize_html(html)
      sanitized_html = Sanitize.fragment(html, Sanitize::Config::RELAXED)
      nokogiri_doc = Nokogiri::HTML(sanitized_html)
      nokogiri_doc.css("script, style").remove
      nokogiri_doc.css("a").each do |link|
        next unless link.get_attribute("href").blank? || link.text.blank?

        link.replace(link.children)
      end

      nokogiri_doc
    end
  end
end
