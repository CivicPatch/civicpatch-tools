# frozen_string_literal: true

require "securerandom"
require "utils/url_helper"
require "core/path_helper"
require_relative "../utils/image_helper"
require "playwright"
require "nokolexbor"

module Browser
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

  def self.with_browser
    Playwright.create(
      playwright_cli_executable_path: Core::PathHelper.project_path(File.join("node_modules", ".bin", "playwright"))
    ) do |playwright|
      browser = playwright.chromium.launch(
        headless: true,
        args: ["--single-process"] # Started happening after upgrading Docker https://github.com/microsoft/playwright/issues/4303
      )
      context = browser.new_context(
        userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" # rubocop:disable Metrics/LineLength
      )

      browser_page = context.new_page

      yield(browser_page)
    end
  end

  def self.fetch_page_content(url, options = {}) # rubocop:disable Metrics/AbcSize
    with_browser do |browser|
      api_data = []

      if options[:include_api_content]
        browser.on("response", lambda { |response|
          content = include_api_content(response)
          api_data << content if content.present?
        })
      end

      with_network_retry(url) do
        return nil if IGNORE_EXTENSIONS.any? { |ext| url.end_with?(ext) }

        browser.goto(url)
        content_type = browser.evaluate("document.contentType")
        return nil unless html_page?(content_type)
      end

      sleep(options[:wait_for]) if options[:wait_for].present?

      yield(browser) if block_given?

      process_page(browser, url, options, api_data)
    end
  end

  private_class_method def self.with_network_retry(url)
    retry_attempts = 0

    begin
      yield
    rescue Net::ReadTimeout, Faraday::TooManyRequestsError
      if retry_attempts < MAX_RETRIES
        sleep_time = BASE_SLEEP**retry_attempts + rand(0..1)
        puts "[429] Rate limited. Retrying in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
        sleep sleep_time
        retry_attempts += 1
        retry
      else
        puts "[429] Too many requests. Max retries reached for #{url}."
        nil
      end
    end
  end

  private_class_method def self.process_page(browser, url, options, api_data)
    page_source = browser.content
    page_source = process_images(browser, page_source, options, url) if options[:image_dir].present?
    format_page_html(page_source, api_data, url)
  end

  private_class_method def self.format_page_html(page_source, api_content, url)
    formatted_html = Utils::UrlHelper.format_links_to_absolute(page_source, url)
    return formatted_html if api_content.empty?

    browser.evaluate("document.body.innerHTML += '#{api_content.join("\n")}'")
    browser.content
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

  private_class_method def self.process_images(browser, page_source, options, url)
    image_dir = options[:image_dir]
    FileUtils.mkdir_p(image_dir)
    base_url = Utils::UrlHelper.extract_page_base_url(page_source, url)
    image_elements = browser.locator("img").all

    image_map = {}

    image_elements.each do |image_element|
      image_excluded = maybe_exclude_image(image_element)
      next if image_excluded

      key, source_image_url = process_image(browser, image_dir, base_url, image_element)
      image_map[key] = source_image_url if key.present? && source_image_url.present?
    end

    # Remove image elements that aren't in the image_map
    page_source = Nokolexbor::HTML(page_source).css("img").each do |img|
      key = image_map.keys.find { |key| img["src"].present? && image_map[key].include?(img["src"]) }

      img.remove unless key.present?
      img["src"] = image_map[key]
    end

    save_image_map(image_dir, image_map)

    page_source.to_html
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

  private_class_method def self.capture_image_as_browser_screenshot(img_element)
    data = img_element.screenshot
    tempfile = Tempfile.new(binmode: true)
    tempfile.write(data)
    tempfile.rewind

    tempfile
  end

  private_class_method def self.process_image(browser, image_dir, base_url, img_element) # rubocop:disable Metrics/AbcSize
    src = img_element.get_attribute("src")
    return if src.nil? || src.empty?

    absolute_src = Utils::UrlHelper.format_url(Addressable::URI.join(base_url, src).to_s)

    file = download_image(absolute_src, browser, img_element)

    raise "File is nil for #{absolute_src}" if file.nil?

    file_type = determine_file_type(file)

    raise "File type is nil for #{absolute_src}" if file_type.nil?

    filename = generate_filename(src, file_type).to_s
    image_path = File.join(image_dir, filename)

    FileUtils.mv(file.path, image_path)

    [filename, absolute_src]
  rescue StandardError => e
    puts "\t\t\t\t❌: Error processing image (#{src}): #{e.message}, removing image element"
    file&.unlink
    nil
  end

  private_class_method def self.maybe_exclude_image(img_element)
    src = img_element.get_attribute("src")
    return false if src.nil? || src.empty?

    if EXCLUDE_IMAGE_PATTERNS.any? { |pattern| src.downcase.include?(pattern) }
      puts "Removed spinner image element with src: #{src}" # Optional logging
      return true # Don't process this element further
    end

    if EXCLUDE_IMAGE_URLS.any? { |url| src.downcase.include?(url) }
      puts "Removed excluded image element with src: #{src}" # Optional logging
      return true # Don't process this element further
    end

    false # Don't process this element further
  end

  private_class_method def self.remove_image_element(img_element)
    img_element.evaluate("el => el.remove()")
  end

  private_class_method def self.download_image(absolute_src, _browser, img_element)
    # Try downloading with HTTParty first
    file = download_with_httparty(absolute_src)
    return file if file

    # If HTTParty failed, try browser screenshot
    file = capture_image_as_browser_screenshot(img_element)

    if file.present?
      puts "\t\t\t✅: Browser screenshot captured for #{absolute_src}"
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
    _fetch_and_follow_redirects(absolute_src, max_redirects)
  end

  private_class_method def self._fetch_and_follow_redirects(initial_url, max_redirects) # rubocop:disable Metrics/CyclomaticComplexity,Metrics/MethodLength,Metrics/PerceivedComplexity,Metrics/AbcSize
    current_url = initial_url
    redirect_count = 0

    while redirect_count < max_redirects
      encoded_url = nil
      begin
        # Normalize URL before each request attempt
        uri = Addressable::URI.parse(current_url).normalize
        encoded_url = uri.to_s
      rescue Addressable::URI::InvalidURIError => e
        puts "Invalid URI during redirect handling for #{initial_url} (current: #{current_url}): #{e.message}"
        return nil # Cannot proceed
      end

      temp_file = Tempfile.new(binmode: true)
      response = nil

      begin
        response = HTTParty.get(encoded_url, timeout: 10, stream_body: true, follow_redirects: false) do |chunk|
          temp_file.write(chunk) unless chunk.empty?
        end
        temp_file.close

        if response.success? # 2xx codes
          return temp_file # Successful download
        elsif [301, 302, 303, 307, 308].include?(response.code)
          # Handle Redirect
          temp_file.unlink # Discard temp file from redirect response
          redirect_count += 1
          location = response.headers["location"]

          if location.blank?
            puts "Redirect from #{encoded_url} missing Location header."
            return nil
          end

          current_url = location # Update URL for the next iteration
          # puts "Redirecting (#{redirect_count}/#{max_redirects}) to: #{current_url}" # Log raw redirect target
          next # Continue to the next loop iteration
        else
          # Handle other HTTP errors (4xx, 5xx)
          puts "\t->HTTP request failed for #{encoded_url} with code: #{response.code}"
          temp_file.unlink
          return nil
        end
      rescue StandardError => e
        # Handle network errors, timeouts, etc.
        puts "\t->HTTParty error for #{encoded_url} (Original: #{initial_url}): #{e.message}"
        temp_file.close
        temp_file.unlink
        return nil
      end
    end

    # If the loop finishes, max redirects were exceeded
    puts "Max redirects (#{max_redirects}) exceeded for original URL: #{initial_url}"
    nil # Return nil explicitly
  end

  private_class_method def self.determine_file_type(file)
    content_type = Utils::ImageHelper.determine_mime_type(file.path)
    extension = Utils::ImageHelper.mime_type_to_extension(content_type)
    if extension.nil?
      puts "\tUnknown file type for #{file.path}: #{content_type}"
      nil
    else
      extension
    end
  end
end
