require_relative "../utils/image_helper"

module Browser
  MAX_RETRIES = 5 # Maximum retry attempts for rate limits
  BASE_SLEEP = 2  # Base sleep time for exponential backoff

  def self.start
    options = Selenium::WebDriver::Chrome::Options.new
    options.add_argument("--headless") # Run without UI
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-blink-features=AutomationControlled") # Avoid bot detection
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

    Selenium::WebDriver.for(:chrome, options: options)
  end

  def self.fetch_page_and_images(url, image_dir)
    FileUtils.mkdir_p(image_dir) unless Dir.exist?(image_dir)
    browser = start

    begin
      browser.get(url)

      wait = Selenium::WebDriver::Wait.new(timeout: 30) # seconds
      wait.until { browser.execute_script("return document.readyState") == "complete" }

      return nil unless html_page?(browser)

      original_page_source = browser.page_source
      base_url = Utils::UrlHelper.extract_page_base_url(original_page_source, url)

      FileUtils.mkdir_p(image_dir)
      image_map = download_images(browser, image_dir, base_url)
      page_source_with_images = browser.page_source

      page_html = Utils::UrlHelper.format_links_to_absolute(page_source_with_images, base_url)

      [page_html, image_map]
    ensure
      browser.quit
    end
  rescue StandardError => e
    puts "Browser fetch failed for #{url}: #{e.message}"
    nil
  end

  def self.fetch_html(url)
    retry_attempts = 0

    begin
      browser = start
      browser.get(url)

      # Wait for document ready AND jQuery AJAX requests to complete (if jQuery is present)
      wait = Selenium::WebDriver::Wait.new(timeout: 30) # seconds
      wait.until do
        browser.execute_script("return document.readyState == 'complete' && (typeof jQuery == 'undefined' || jQuery.active == 0)")
      end

      browser.page_source
    rescue Net::ReadTimeout, Faraday::TooManyRequestsError => e
      if retry_attempts < MAX_RETRIES
        sleep_time = BASE_SLEEP**retry_attempts + rand(0..1) # Exponential backoff with jitter
        puts "[429] Rate limited. Retrying in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
        sleep sleep_time
        retry_attempts += 1
        retry
      else
        puts "[429] Too many requests. Max retries reached for #{url}."
      end
    rescue StandardError => e
      puts "Browser fetch failed for #{url}: #{e.message}"
      nil
    ensure
      browser.quit
    end
  end

  def self.html_page?(browser)
    content_type = browser.execute_script("return document.contentType")

    return false if content_type.blank?

    content_type.downcase.include?("text/html")
  end

  def self.download_images(browser, image_dir, base_url)
    image_elements = browser.find_elements(tag_name: "img")

    image_map = {}

    image_elements.each do |image_element|
      key, source_image = process_image(browser, image_dir, base_url, image_element)
      image_map[key] = source_image if key.present? && source_image.present?
    end

    image_map
  end

  def self.generate_filename(src, file_type)
    hash = Digest::SHA256.hexdigest(src)
    "#{hash}.#{file_type}"
  end

  def self.capture_image_as_data_url(browser, img_element)
    # Set crossorigin attribute before attempting to draw to canvas
    browser.execute_script("
      const img = arguments[0];
      // Add crossorigin attribute to allow canvas operations
      img.setAttribute('crossorigin', 'anonymous');

      // Small delay to let browser apply the attribute
      return new Promise((resolve) => {
        setTimeout(() => {
          try {
            const canvas = document.createElement('canvas');
            canvas.width = img.naturalWidth || 300;
            canvas.height = img.naturalHeight || 150;
            const ctx = canvas.getContext('2d');
            ctx.drawImage(img, 0, 0);
            resolve(canvas.toDataURL('image/jpeg'));
          } catch (e) {
            // Return error message if canvas is tainted
            resolve('ERROR: ' + e.message);
          }
        }, 100);
      });
    ", img_element)
  end

  def self.save_image_from_data_url(data_url)
    # Strip data URL prefix to get base64 data
    return nil unless data_url.start_with?("data:image/")

    base64_data = data_url.split(",")[1]

    # Save image file
    downloaded_file = Tempfile.new(binmode: true)
    downloaded_file.write(Base64.decode64(base64_data))
    downloaded_file.close

    downloaded_file
  end

  def self.process_image(browser, image_dir, base_url, img_element)
    src = img_element.attribute("src")
    return if src.nil? || src.empty?

    # Pre-processing: Skip common spinner images
    spinner_patterns = ["loading.gif", "spinner.gif", "ajax-loader.gif", "loader.gif"]
    if spinner_patterns.any? { |spinner| src.downcase.include?(spinner) }
      # Remove the element from the DOM
      browser.execute_script("arguments[0].remove()", img_element)
      puts "Removed spinner image element with src: #{src}" # Optional logging
      return # Don't process this element further
    end

    absolute_src = Addressable::URI.join(base_url, src).to_s

    file = download_with_httparty(absolute_src)
    unless file
      data_url = capture_image_as_data_url(browser, img_element)
      if data_url.start_with?("ERROR:")
        puts "Canvas error for #{src}: #{data_url}"
        return
      end
      file = save_image_from_data_url(data_url)
    end

    file_type = determine_file_type(file)

    return if file_type.nil?

    filename = generate_filename(src, file_type)
    image_path = File.join(image_dir, filename)

    FileUtils.mv(file.path, image_path)

    browser.execute_script("arguments[0].setAttribute('src', arguments[1])",
                           img_element, filename)

    [filename, absolute_src]
  rescue StandardError => e
    puts "Error processing image (#{src}): #{e.message}"
  end

  def self.download_with_httparty(absolute_src)
    # Handle relative URLs
    # Skip data URLs
    return false if absolute_src.start_with?("data:")

    downloaded_file = Tempfile.new(binmode: true)
    response = HTTParty.get(absolute_src, timeout: 5, stream_body: true) do |chunk|
      next if [301, 302].include?(chunk.code)

      downloaded_file.write(chunk)
    end

    downloaded_file.close

    downloaded_file if response.success?
  rescue StandardError => e
    puts "HTTParty error for #{absolute_src}: #{e.message}"
    nil
  end

  def self.determine_file_type(file)
    content_type = Utils::ImageHelper.determine_mime_type(file.path)
    extension = Utils::ImageHelper.mime_type_to_extension(content_type)
    if extension.nil?
      puts "Unknown file type for #{file.path}: #{content_type}"
      nil
    else
      extension
    end
  end
end
