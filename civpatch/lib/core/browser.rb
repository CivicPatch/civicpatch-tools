# frozen_string_literal: true

require "securerandom"
require "utils/url_helper"
require "core/path_helper"
require_relative "../utils/image_helper"
require "playwright"
require "nokolexbor"

module Core
  class Browser
    PLAYWRIGHT_SCRIPT = Core::PathHelper.project_path(File.join("lib", "core", "browser", "scraper.js"))
    MAX_RETRIES = 5 # Maximum retry attempts for rate limits
    BASE_SLEEP = 2  # Base sleep time for exponential backoff
    EXCLUDE_IMAGE_URLS = ["tile.openstreetmap.org"].freeze
    EXCLUDE_IMAGE_PATTERNS = ["spinner.gif", "loading.gif", "ajax-loader.gif", "loader.gif"].freeze
    INCLUDE_API_CONTENT = {
      mwjsPeople: {
        pattern: "mwjsPeople",
        start_string: "var mwjsMemberData=",
        end_string: ",onerror"
      }
    }.freeze
    IGNORE_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx"].freeze
    USER_AGENTS = [
      "Dalvik/2.1.0 (Linux; U; Android 10; MI MAX 3 MIUI/20.1.16)",
      "Mozilla/5.0 (Linux; Android 9; SM-A750G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.74 Mobile Safari/537.36",
      "Mozilla/5.0 (Linux; Android 9; SM-J701F Build/PPR1.180610.011; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/91.0.4472.120 Mobile Safari/537.36",
      "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko; Google Web Preview) Chrome/89.0.4389.84 Safari/537.36",
      "Mozilla/5.0 (Windows NT 10.0; rv:77.0) Gecko/20100101 Firefox/77.0 anonymized by Abelssoft 462766946"
    ]

    def self.with_browser
      Playwright.create(
        playwright_cli_executable_path: Core::PathHelper.project_path(File.join("node_modules", ".bin", "patchright"))
      ) do |playwright|
        browser = playwright.chromium.launch(
          headless: false,
          args: ["--single-process"]
        )

        browser_page = browser.new_page

        yield(browser_page)
      end
    end

    def self.fetch_page_content(url, options = {})
      with_browser do |page|
        api_data = []

        if options[:include_api_content]
          page.on("response", lambda { |response|
            content = include_api_content(response)
            api_data << content if content.present?
          })
        end

        with_network_retry(url) do
          return nil if IGNORE_EXTENSIONS.any? { |ext| url.end_with?(ext) }

          page.goto(url)
          content_type = page.evaluate("document.contentType")
          return nil unless html_page?(content_type)
        end

        sleep(options[:wait_for]) if options[:wait_for].present?

        yield(page) if block_given?

        process_page(page, url, options, api_data)
      end
    end

    private_class_method def self.with_network_retry(url)
      retry_attempts = 0

      begin
        yield
      rescue StandardError => e
        if retry_attempts < MAX_RETRIES
          sleep_time = BASE_SLEEP**retry_attempts + rand(0..1)
          puts "Error trying to fetch page: #{e.message}"
          puts "Retrying in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
          sleep sleep_time
          retry_attempts += 1
          retry
        else
          puts "Too many requests. Max retries reached for #{url}."
          nil
        end
      end
    end

    private_class_method def self.process_page(page, url, options, api_data)
      page_source = page.content

      page_source = process_images(page, page_source, options, url) if options[:image_dir].present?
      page_source = Utils::UrlHelper.format_links_to_absolute(page_source, url)
      page_source = format_page_html(page_source, api_data, url) if api_data.present?

      page_source
    rescue StandardError => e
      puts "Error processing page: #{e.message}, skipping"
      puts e.backtrace
      nil
    end

    private_class_method def self.format_page_html(page_source, api_content, url)
      doc = Nokolexbor::HTML(page_source)
      body = doc.at_css("body")
      body.add_child(Nokolexbor::HTML.fragment(api_content))

      doc.to_html
    end

    private_class_method def self.log_error(url, error)
      puts error.backtrace
      puts "Browser fetch failed for #{url}: #{error.message}"
    end

    private_class_method def self.html_page?(content_type)
      return false if content_type.blank?

      content_type.downcase.include?("text/html")
    end

    private_class_method def self.include_api_content(response)
      return unless response.url.include?(INCLUDE_API_CONTENT[:mwjsPeople][:pattern])

      begin
        text = response.text
      rescue StandardError => e
        puts "Error getting response text: #{e.message}"
        puts e.backtrace
        return nil
      end

      extract_api_content(INCLUDE_API_CONTENT[:mwjsPeople][:pattern], text)
    end

    private_class_method def self.extract_api_content(pattern, text)
      INCLUDE_API_CONTENT.each_value do |config|
        next unless config[:pattern] == pattern

        start_string = config[:start_string] || "="
        end_string = config[:end_string] || "(?:\\s*;|\\n|$)"
        pattern_regex = /#{start_string}\s*(.+?)#{end_string}/m

        matches = text.match(pattern_regex)
        next unless matches && matches[1]

        extracted_content = matches[1].strip
        puts "Extracted content: #{extracted_content}"
        return extracted_content
      end

      nil
    end

    private_class_method def self.process_images(page, page_source, options, url)
      prepare_browser_screenshot(page)
      image_dir = options[:image_dir]
      FileUtils.mkdir_p(image_dir)
      base_url = Utils::UrlHelper.extract_page_base_url(page_source, url)
      image_elements = page.locator("img").all

      image_map = {}

      image_elements.each do |image_element|
        image_excluded = maybe_exclude_image(image_element)
        next if image_excluded

        key, source_image_url = process_image(page, image_dir, base_url, image_element)
        image_map[key] = source_image_url if key.present? && source_image_url.present?
      end

      # Remove image elements that aren't in the image_map
      document = Nokolexbor::HTML(page_source)

      document.css("img").each do |img|
        key = image_map.keys.find { |key| img["src"].present? && image_map[key].include?(img["src"]) }

        img.remove unless key.present?
        img["src"] = image_map[key]
      end

      save_image_map(image_dir, image_map)

      document.to_html
    end

    private_class_method def self.save_image_map(image_dir, image_map)
      file_path = File.join(image_dir, "image_map.json")
      if File.exist?(file_path)
        existing_map = JSON.parse(File.read(file_path))
        image_map = existing_map.merge(image_map)
      end

      File.write(file_path, JSON.generate(image_map))
    end

    private_class_method def self.generate_filename(src, file_type)
      hash = Digest::SHA256.hexdigest(src)
      "#{hash}.#{file_type}"
    end

    private_class_method def self.process_image(page, image_dir, base_url, img_element) # rubocop:disable Metrics/AbcSize
      src = img_element.get_attribute("src")
      return if src.nil? || src.empty?

      absolute_src = Utils::UrlHelper.format_url(Addressable::URI.join(base_url, src).to_s)

      file = download_image(page, absolute_src, img_element)

      raise "File is nil for #{absolute_src}" if file.nil?

      file_type = determine_file_type(file)

      raise "File type is nil for #{absolute_src}" if file_type.nil?

      filename = generate_filename(src, file_type).to_s
      image_path = File.join(image_dir, filename)

      FileUtils.mv(file.path, image_path)

      [filename, absolute_src]
    rescue StandardError => e
      puts "\t\t\t\t❌: Error processing image (#{absolute_src}): #{e.message}, removing image element"
      file&.unlink
      nil
    end

    private_class_method def self.maybe_exclude_image(img_element)
      src = img_element.get_attribute("src")
      return false if src.nil? || src.empty?

      if EXCLUDE_IMAGE_PATTERNS.any? { |pattern| src.downcase.include?(pattern) }
        # puts "Removed spinner image element with src: #{src}" # Optional logging
        return true # Don't process this element further
      end

      if EXCLUDE_IMAGE_URLS.any? { |url| src.downcase.include?(url) }
        # puts "Removed excluded image element with src: #{src}" # Optional logging
        return true # Don't process this element further
      end

      false # Don't process this element further
    rescue StandardError => e
      puts "maybe_exclude_image err: #{e.message}"
      false
    end

    private_class_method def self.remove_image_element(img_element)
      img_element.evaluate("el => el.remove()")
    end

    private_class_method def self.download_image(page, absolute_src, img_element)
      # Try downloading with HTTParty first
      file = download_with_httparty(absolute_src)
      return file if file

      # If HTTParty failed, try browser screenshot
      file = capture_image_as_browser_screenshot(page, img_element)

      if file.present?
        # puts "\t\t\t✅: Browser screenshot captured for #{absolute_src}"
      else
        puts "\t\t\t❌: Screenshot capture failed for #{absolute_src}, giving up"
        return nil
      end

      file
    end

    private_class_method def self.download_with_httparty(absolute_src)
      # Skip data URLs
      return nil if absolute_src.start_with?("data:")

      max_redirects = 5
      url = absolute_src

      max_redirects.times do
        uri = Addressable::URI.parse(url).normalize
        temp_file = Tempfile.new(binmode: true)
        response = HTTParty.get(
          uri.to_s, {
            headers: { "User-Agent" => USER_AGENTS.sample },
            timeout: 10,
            stream_body: true,
            follow_redirects: false
          }
        ) do |chunk|
          temp_file.write(chunk) unless chunk.empty?
        end
        temp_file.close

        case response.code
        when 200..299
          return temp_file
        when 301, 302, 303, 307, 308
          temp_file.unlink
          url = response.headers["location"]
          break if url.blank?
        else
          temp_file.unlink
          break
        end
      rescue StandardError
        break
      end
    end

    private_class_method def self.prepare_browser_screenshot(page)
      # Popups might interfere with screenshot capture, so we try to close them first

      page.evaluate <<~JS
        [
          '[role="dialog"]',
          '[aria-modal="true"]',
          '[class*="modal"]',
          '[class*="popup"]',
          '[class*="overlay"]',
          '[id*="modal"]',
          '[id*="popup"]',
          '[id*="overlay"]',
          '.cookie',
          '.consent'
        ].forEach(selector => {
          document.querySelectorAll(selector).forEach(el => {
            el.style.display = 'none';
          });
        });
      JS
    rescue StandardError
      # Ignore if not present
    end

    private_class_method def self.capture_image_as_browser_screenshot(page, img_element)
      data = img_element.screenshot
      tempfile = Tempfile.new(binmode: true)
      tempfile.write(data)
      tempfile.rewind

      tempfile
    end

    private_class_method def self.determine_file_type(file)
      content_type = Utils::ImageHelper.determine_mime_type(file.path)
      extension = Utils::ImageHelper.mime_type_to_extension(content_type)
      if extension.nil?
        # puts "\tUnknown file type for #{file.path}: #{content_type}"
        nil
      else
        extension
      end
    end
  end
end
