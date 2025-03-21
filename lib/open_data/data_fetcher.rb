require "capybara"
require "selenium-webdriver"

class DataFetcher
  # TODO: -- robots.txt?
  def extract_content(url, destination_dir)
    using_browser = false
    browser_session = nil

    begin
      html = fetch_with_client(url)
    rescue => e

      puts "Error fetching HTML: #{e.message}"

      puts "Retrying with browser..."

      configure_browser
      using_browser = true
      html, browser_session = fetch_with_browser(url)

      puts "Fetched with browser"
    end

    FileUtils.mkdir_p(destination_dir)
    FileUtils.mkdir_p(Rails.root.join(destination_dir, "images"))

    File.write(Rails.root.join("#{destination_dir}", "step_1_original_html.html"), html)

    base_url, cleaned_html = clean_html(url, html, destination_dir)

    download_images(base_url, cleaned_html, Rails.root.join(destination_dir, "images"), using_browser, browser_session)
    update_html_links(base_url, cleaned_html)

    File.write(Rails.root.join("#{destination_dir}", "step_2_cleaned_html.html"), cleaned_html.to_html)

    markdown_content = Markitdown.from_nokogiri(cleaned_html)

    File.write(Rails.root.join("#{destination_dir}", "step_3_markdown_content.md"), markdown_content)

    content_file = Rails.root.join("#{destination_dir}", "step_3_markdown_content.md")


    if using_browser
      browser_session.quit
    end

    content_file
  end

  private

  def clean_html(page_url, html, destination_dir)
    nokogiri_html = Nokogiri::HTML(html)
    # important for images to work -- don't want to clean it away and lose context
    base_url = get_page_base_url(nokogiri_html, page_url)

    found_element = nil
      selectors = [
        "#main-content", "#content-main", "#primary-content",
        "#content", "#page-content",
        "main.content",
        "main",
        "div.article", "div.main",
        "#container-content",
        "#container",
        "#wrapper-content",
        "#wrapper",
        "#body-content",
        "#body",
        "#page",
        "body", "html"
      ]

      # Try each selector individually to see which one matches
      selectors.each do |selector|
        element = nokogiri_html.css(selector).first
        if element &&
           ![ "a", "img", "button", "span", "input",
            "iframe", "script", "style", "meta", "link", "br", "hr" ].include?(element.name)
          puts "Matched selector: #{selector}"
          puts "Element name: #{element.name}"
          puts "Element classes: #{element['class']}"
          puts "Element ID: #{element['id']}"
          puts "Element content length: #{element.content.length}"
          found_element = element
          break
        end
      end

      # raise an error if no selector matches
      if found_element.nil?
        raise "No selector matched"
      end

    strip_html_content(found_element)
    [ base_url, found_element ]
  end

  def download_images(base_url, nokogiri_html, destination_dir, using_browser, browser_session)
    nokogiri_html.css("img").each_with_index do |img, index|
      image_url = img["src"]
      image_url = format_url(image_url)

      absolute_image_url = URI.join(base_url, image_url).to_s

      # hash the image url
      image_hash = Digest::SHA256.hexdigest(absolute_image_url)
      # determine the extension from the url
      extension = File.extname(absolute_image_url)

      filename = "#{image_hash}#{extension}"

      # filename = File.basename(absolute_image_url)
      ## get rid of query params
      # filename = filename.split("?").first

      destination_path = File.join(destination_dir, filename)

      begin
        File.open(destination_path, "wb") do |file|
          image_content = using_browser ? get_image_with_browser(browser_session, absolute_image_url) : get_image(absolute_image_url)
          file.write(image_content)
        end

        # update the img tag to point to the local file
        img["src"] = "images/#{filename}"
      rescue => e
        puts "Error downloading image: #{e.message}"
        puts "Image URL: #{absolute_image_url}"
        puts "Destination path: #{destination_path}"
      end
    end
  end

  def update_html_links(base_url, nokogiri_html)
    nokogiri_html.css("a").each do |link|
      if link["href"].blank?
        next
      end

      link["href"] = format_url(link["href"])

      begin
        link["href"] = URI.join(base_url, link["href"]).to_s
      rescue => e
        puts "Error updating link: #{e.message}"
        puts "Link: #{link["href"]}"
        link["href"] = nil
      end
    end
  end

  def get_image(image_url)
    HTTParty.get(image_url).body
  end

  def get_image_with_browser(session, image_url)
    session.visit(image_url)

    # Ensure the image is loaded before extracting
    session.assert_selector("img", wait: 5)  # Waits up to 5 seconds for an <img> tag


    # Extract image binary data
    image_data_base64 = session.evaluate_script(%(
      (function() {
        var img = document.querySelector("img");
        if (img) {
          var canvas = document.createElement("canvas");
          var ctx = canvas.getContext("2d");
          canvas.width = img.naturalWidth;
          canvas.height = img.naturalHeight;
          ctx.drawImage(img, 0, 0);
          return canvas.toDataURL("image/png").split(",")[1]; // Get Base64 data
        }
        return null;
      })();
    ))

    Base64.decode64(image_data_base64)
  end

  private

  def fetch_with_client(url)
    response = HTTParty.get(url, headers: {
      "User-Agent" => "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
      "Accept-Language" => "en-US,en;q=0.9",
      "Accept" => "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
      "Referer" => "https://www.brave.com/"
      },
      )

    if response.code == 403
      raise "fetch_with_client: Access Denied by #{url}"
    end

    response.body
  end

  def fetch_with_browser(url)
    session = Capybara::Session.new(:selenium_chrome)
    session.visit(url)

    sleep 5

    html = session.html

    [ html, session ]
  end

  def strip_html_content(nokogiri_html)
    nokogiri_html.css("script, style, svg, nav, header, head, footer").remove

    # Remove empty paragraphs and divs
    nokogiri_html.css('.ad, .advertisement, [class*="ad-"], [id*="ad-"]').remove
    nokogiri_html.css('.cookie-banner, .consent-banner, [class*="cookie"], [class*="consent"]').remove
    nokogiri_html.css('.modal, .popup, [class*="overlay"], [class*="modal"]').remove
    nokogiri_html.css('.share-buttons, [class*="social-share"], [class*="share"]').remove
    nokogiri_html.css('.related-content, .recommended, [class*="related"]').remove
    nokogiri_html.css('.newsletter, [class*="subscribe"], [class*="signup"]').remove

    nokogiri_html.css('.pagination, .pager, [class*="page-nav"]').remove
    nokogiri_html.css('.print, .download, [class*="print"], [class*="download"]').remove
    nokogiri_html.css('.breadcrumb, .breadcrumbs, [class*="breadcrumb"]').remove
    nokogiri_html.css('.byline, .author-info, [class*="author"], [class*="byline"]').remove
    nokogiri_html.css('#comments, .comment-section, [class*="comment"]').remove
    nokogiri_html.css('.sidebar, .sidebar-module, [class*="sidebar"]').remove
    nokogiri_html.css('.newsletter, [class*="newsletter"], [id*="newsletter"], .archive-links, .drawer, .accordion, .collapsible').remove

    nokogiri_html.css("li a").each do |link|
      link.parent.remove if link.text.include?("News Update")
    end
    nokogiri_html.css('a[href*="News Update"]').remove

    # Remove comments
    nokogiri_html.xpath("//comment()").remove
    nokogiri_html.xpath("//text()").each do |node|
      node.remove if node.text.strip.empty?
    end
    nokogiri_html.xpath("//*[@aria-label]").each { |node| node.remove_attribute("aria-label") }

    # Remove empty tags. If there are any image tags, don't remove the node
    nokogiri_html.css("p, div").each do |node|
      if node.text.strip.empty?
        if node.css("img").any?
          next
        end
        node.remove
      end
    end

    nokogiri_html.css(".b, .b-c, .g").each { |node| node.replace(node.inner_html) }
    nokogiri_html.css("*").each { |node| node.remove_attribute("class") }
  end

  def configure_browser
    Capybara.register_driver :selenium_chrome do |app|
      options = Selenium::WebDriver::Chrome::Options.new
      options.add_argument("--disable-gpu")
      options.add_argument("--no-sandbox")
      options.add_argument("--disable-dev-shm-usage")
      options.add_argument("--headless") unless ENV["SHOW_BROWSER"]
      # set user agent to headed chrome
      options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

      Capybara::Selenium::Driver.new(app, browser: :chrome, options: options)
    end
  end

  # base here means the base url as it relates to the html page
  # sometimes the base will be rewritten in the html, so links are relative to the base
  def get_page_base_url(nokogiri_html, page_url)
    base_override_url  = nokogiri_html.css("base").first&.attr("href")
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
    # handle spaces
    url.gsub(" ", "%20")
  end
end
