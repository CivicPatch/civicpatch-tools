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
      browser.navigate.to(url)
      base_url = detect_base_url(browser, url)

      img_elements = browser.find_elements(tag_name: 'img')

      img_elements.each do |img_element|
        process_image(browser, img_element, image_dir, base_url)
      end

      browser.page_source
    ensure
      browser.quit
    end
  end

  def self.detect_base_url(browser, default_url)
    base_elements = browser.find_elements(tag_name: "base")

    if !base_elements.empty? && base_elements[0].attribute('href')
      base_href = base_elements[0].attribute("href")
      base_href += "/" unless base_href.end_with?("/")
      base_href
    else
      default_url
    end
  end

  def self.fetch_html(url)
    retry_attempts = 0

    begin
      browser = start
      browser.navigate.to(url)
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

  def self.generate_filename(src)
    match = src.match(%r{([^/]+\.(jpg|jpeg|png|gif|webp))$}i)
    hash = Digest::SHA256.hexdigest(src)

    if match
      "#{hash}.#{match[1]}"
    else
      "#{hash}.jpg" # TODO: Be more accurate
    end
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

  def self.save_image_from_data_url(data_url, image_path)
    # Strip data URL prefix to get base64 data
    if data_url.start_with?("data:image/")
      base64_data = data_url.split(",")[1]

      # Save image file
      File.open(image_path, "wb") do |f|
        f.write(Base64.decode64(base64_data))
      end
      return true
    end
    false
  end

  def self.process_image(browser, img_element, image_dir, base_url)
    begin
      src = img_element.attribute('src')
      return if src.nil? || src.empty?

      filename = generate_filename(src)
      image_path = File.join(image_dir, filename)

      absolute_src = Addressable::URI.join(base_url, src).to_s

      if download_with_httparty(absolute_src, image_path, base_url)
        browser.execute_script("arguments[0].setAttribute('src', arguments[1])",
                             img_element, filename)
      else
        # Fallback to canvas method
        data_url = capture_image_as_data_url(browser, img_element)

        if data_url.start_with?('ERROR:')
          puts "Canvas error for #{src}: #{data_url}"
          return
        end

        if save_image_from_data_url(data_url, image_path)
          browser.execute_script("arguments[0].setAttribute('src', arguments[1])", 
                               img_element, filename)
        end
      end
    rescue => e
      puts "Error processing image (#{src}): #{e.message}"
    end
  end

  def self.download_with_httparty(src_url, image_path, referrer)
    begin
      # Handle relative URLs
      src_url = make_absolute_url(src_url, referrer) unless src_url.start_with?("http")
      # Skip data URLs
      return false if src_url.start_with?("data:")

      response = HTTParty.get(src_url, timeout: 5)

      # Check if request was successful
      if response.code == 200
        # Save image content
        File.open(image_path, 'wb') do |file|
          file.write(response.body)
        end
        return true
      end

      # Return false if status code wasn't 200
      puts "HTTParty request failed with code #{response.code} for #{src_url}"
      return false
    rescue => e
      puts "HTTParty error for #{src_url}: #{e.message}"
      return false
    end
  end
end
