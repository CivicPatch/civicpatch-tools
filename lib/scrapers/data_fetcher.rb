# frozen_string_literal: true

require "capybara"
require "selenium-webdriver"

require_relative "./common"
require_relative "../core/browser"

module Scrapers
  class DataFetcher
    # TODO: -- robots.txt?
    def extract_content(url, destination_dir)
      puts "Extracting content from #{url}"

      html = fetch_html(url)

      FileUtils.mkdir_p(destination_dir)
      FileUtils.mkdir_p(PathHelper.project_path(File.join(destination_dir, "images")))

      File.write(PathHelper.project_path(File.join(destination_dir.to_s, "step_1_original_html.html")), html)

      base_url, parsed_html = parse_html(url, html)

      download_images(base_url, parsed_html, PathHelper.project_path(File.join(destination_dir, "images")))
      update_html_links(base_url, parsed_html)
      rewrite_script_tags(parsed_html)

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

    def download_images(base_url, nokogiri_html, destination_dir)
      nokogiri_html.css("img").each_with_index do |img, _index|
        image_url = img["src"]

        next if image_url.blank? || image_url.start_with?("data:image")

        image_url = format_url(image_url)

        # Use safe join and encoding
        absolute_image_url = Addressable::URI.parse(base_url).join(image_url).to_s

        # hash the image url
        image_hash = Digest::SHA256.hexdigest(absolute_image_url)

        filename = File.basename(absolute_image_url)
        # get rid of query params
        filename = filename.split("?").first
        extension = File.extname(filename)

        filename = "#{image_hash}#{extension}"

        destination_path = File.join(destination_dir, filename)

        File.open(destination_path, "wb") do |file|
          image_content = get_image(absolute_image_url)
          file.write(image_content)
        end

        # update the img tag to point to the local file
        img["src"] = "images/#{filename}"
      rescue StandardError => e
        puts "Error downloading image: #{e.message}"
        puts "Image URL: #{absolute_image_url}"
        puts "Destination path: #{destination_path}"
      end
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

    def rewrite_script_tags(nokogiri_html)
      nokogiri_html.css("script").each do |script|
        script.replace("<pre class='script-content'>#{script.to_html.gsub("<", "&lt;").gsub(">", "&gt;")}</pre>")
      end
    end

    def get_image(image_url)
      encoded_image_url = Addressable::URI.parse(image_url).normalize.to_s
      HTTParty.get(encoded_image_url).body
    end

    def fetch_html(url)
      response = HTTParty.get(url)

      raise "fetch_with_client: Access Denied by #{url}" if response.code == 403

      response.body
    rescue StandardError
      Browser.fetch_html(url)
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
      Scrapers::Common.format_url(url)
    end
  end
end
