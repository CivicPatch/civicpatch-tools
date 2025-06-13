# frozen_string_literal: true

require "capybara"
require "selenium-webdriver"
require "sanitize"
require "rbconfig"

require "utils/url_helper"
require_relative "../core/browser"

module Core
  class PageFetcher
    WAIT_TIME = 2
    HTML_2_MARKDOWN_PATH = Core::PathHelper.project_path(File.join("lib", "utils", "html2markdown"))

    def self.extract_content(url, destination_dir)
      cached_file = Core::PathHelper.project_path(File.join(destination_dir.to_s, "step_3_markdown_content.md"))

      if File.exist?(cached_file)
        puts "Skipping page fetch to #{url} because cache file already exists"
        return cached_file
      end

      # Store images one level up from destination dir to simplify image upload
      image_dir = PathHelper.project_path(File.join(destination_dir, "..", "images"))
      page_html = Core::Browser.fetch_page_content(url, { image_dir: image_dir,
                                                          wait_for: WAIT_TIME,
                                                          include_api_content: true })
      return nil if page_html.blank?

      html = page_html

      return nil if html.blank?

      FileUtils.mkdir_p(destination_dir)

      File.write(Core::PathHelper.project_path(File.join(destination_dir.to_s, "step_1_original_html.html")), html)

      sanitized_doc = sanitize_html(html)

      File.write(Core::PathHelper.project_path(File.join(destination_dir.to_s, "step_2_sanitized_html.html")),
                 sanitized_doc.to_html)

      markdown_content = html_to_markdown(sanitized_doc.to_html)
      markdown_content_file_path = Core::PathHelper.project_path(File.join(destination_dir.to_s,
                                                                           "step_3_markdown_content.md"))
      File.write(markdown_content_file_path, markdown_content)

      Core::PathHelper.project_path(markdown_content_file_path)
    end

    def self.markdown_executable_path
      host_os = RbConfig::CONFIG["host_os"]

      if host_os =~ /darwin/i
        File.join(HTML_2_MARKDOWN_PATH, "html2markdown_macos")
      elsif host_os =~ /linux/i
        File.join(HTML_2_MARKDOWN_PATH, "html2markdown_linux")
      elsif host_os =~ /mswin|mingw|cygwin/i
        File.join(HTML_2_MARKDOWN_PATH, "html2markdown_windows.exe")
      else
        raise "Unsupported OS: #{host_os}. Only x64 versions of macOS, Linux, and Windows are supported."
      end
    end

    def self.html_to_markdown(html)
      executable_path = markdown_executable_path
      raise "Markdown executable not found at #{executable_path}" unless File.exist?(executable_path)

      output = IO.popen([executable_path], "r+", err: %i[child out]) do |io|
        io.write(html)
        io.close_write
        result = io.read
        result
      end

      raise "Failed to convert HTML to Markdown: #{output}" unless $?.success?

      output.strip
    end

    def self.sanitize_html(html)
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
