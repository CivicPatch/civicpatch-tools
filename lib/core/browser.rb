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

  def self.fetch_html(url)
    retry_attempts = 0

    begin
      browser = start
      browser.navigate.to(url)
      browser.page_source
    rescue Faraday::TooManyRequestsError => e
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

  def self.fetch_image(url)
    raise NotImplementedError
  end
end
