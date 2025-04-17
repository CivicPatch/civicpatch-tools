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
    # TODO: -- robots.txt?
    def extract_content(url, destination_dir)
      cached_file = PathHelper.project_path(File.join(destination_dir.to_s, "step_3_markdown_content.md"))

      if File.exist?(cached_file)
        puts "Skipping page fetch to #{url} because cache file already exists"
        return cached_file
      end

      FileUtils.mkdir_p(destination_dir)
      image_dir = PathHelper.project_path(File.join(destination_dir, "images"))
      FileUtils.mkdir_p(image_dir)

      html = Browser.fetch_page_and_images(url, image_dir)
      html = with_prefixed_image_urls(html)
      html = Sanitize.fragment(html, Sanitize::Config::RELAXED)

      File.write(PathHelper.project_path(File.join(destination_dir.to_s, "step_1_original_html.html")), html)

      base_url, parsed_html = parse_html(url, html)

      update_html_links(base_url, parsed_html)

      File.write(PathHelper.project_path(File.join(destination_dir.to_s, "step_2_parsed_html.html")),
                 parsed_html.to_html)

      markdown_content = Markitdown.from_nokogiri(parsed_html)

      File.write(PathHelper.project_path(File.join(destination_dir.to_s, "step_3_markdown_content.md")),
                 markdown_content)

      PathHelper.project_path(File.join(destination_dir.to_s, "step_3_markdown_content.md"))
    end

    private

    def parse_html(page_url, html)
      nokogiri_html = Nokogiri::HTML(html)
      # important for images to work -- don't want to clean it away and lose context
      base_url = get_page_base_url(nokogiri_html, page_url)
      [base_url, nokogiri_html]
    end

    def with_prefixed_image_urls(html)
      doc = Nokogiri::HTML(html)
      # for all image tags, prefix the src string with images
      doc.css("img").each do |img|
        next if img["src"].blank?

        img["src"] = "images/#{img["src"]}"
      end

      doc.to_html
    end

    def update_html_links(base_url, nokogiri_html)
      nokogiri_html.css("a").each do |link|
        next if link["href"].blank?

        # ignore if the link is a mailto link
        next if link["href"].starts_with?("mailto:")

        # remove non-ascii characters
        link["href"] = link["href"].gsub(/[^\x00-\x7F]/, "")

        link["href"] = format_url(link["href"])

        begin
          link["href"] = Addressable::URI.parse(base_url).join(link["href"]).to_s
        rescue StandardError => e
          puts "Error updating link: #{e.message}"
          puts "Link: #{link["href"]}"
          link["href"] = nil
        end
      end
    end

    # base here means the base url as it relates to the html page
    # sometimes the base will be rewritten in the html, so links are relative to the base
    def get_page_base_url(nokogiri_html, page_url)
      base_override_url = nokogiri_html.css("base").first&.attr("href")
      if base_override_url == "/"
        # To get both scheme and host, we need to combine them
        # For example, for "https://www.seattle.gov/council/meet-the-council"
        # URI.parse(page_url).scheme returns "https"
        # URI.parse(page_url).host returns "www.seattle.gov"
        uri = URI.parse(page_url)

        base_override_url = "#{uri.scheme}://#{uri.host}"
      end

      base_override_url || page_url
    end

    def format_url(url)
      Utils::UrlHelper.format_url(url)
    end
  end
end
