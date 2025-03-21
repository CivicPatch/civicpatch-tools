require "capybara"
require "selenium-webdriver"

class MapFinder
  def initialize(state, city)
    @state = state
    @city = city

    configure_capybara

    # create output directory if it doesn't exist
    @destination_dir = Rails.root.join("data", @state, @city, "cache")
    FileUtils.mkdir_p(@destination_dir)

    @session = Capybara::Session.new(:selenium_chrome)
  end

  # maps may be arcgis or, for example chicago, from openstreetmaps.
  # let's focus on just arcgis -- that seems to be overwhelmingly popular
  # flag the ones that don't match for manual verification
  def find_candidate_maps(candidate_url, type = "district") # could also be "ward"
    puts "Finding candidate maps for #{candidate_url}"
    # source 1: maybe we are already on the map page
    candidate_uri = URI.parse(candidate_url)
    if candidate_uri.host.ends_with?("arcgis.com")
      candidate_urls = get_network_map_urls(candidate_url)
    end

    # source 2: check if url contains iframe with src that contains arcgis
    # source 3: check if url contains link with href that contains arcgis
    # source 4: maybe there is a link on the page containing "district(s) | ward(s) map"
    @session.quit

    candidate_urls || []
  end

  def download_geojson_urls(urls)
    puts "Downloading #{urls.count} geojson files"

    context = []
    urls.each_with_index do |url, index|
      puts "Downloading #{url}"
      file_name = "candidate_map_#{index}.geojson"
      file_path = Rails.root.join(@destination_dir, file_name)
      context << { url: url, file_path: file_path }

      File.write(file_path, HTTParty.get(url).body)
    end

    context
  end

  def self.format_properties(state, city, geojson_file_path, fields_to_keep)
    geojson = JSON.parse(File.read(geojson_file_path))

    filtered_features = geojson["features"].map do |feature|
      properties = feature["properties"]
      property_keys = properties.keys

      remapped_properties = {}

      fields_to_keep.each do |target_field|
        match = self.best_match(target_field, property_keys)
        remapped_properties[target_field] = properties[match] if match
      end

      {
        "type" => "Feature",
        "geometry" => feature["geometry"],
        "properties" => remapped_properties
      }
    end

    filtered_geojson = {
      "type" => "FeatureCollection",
      "features" => filtered_features
    }.to_json

    filtered_geojson
  end


  private

  def get_network_map_urls(url)
    candidate_urls = []
    # get all urls from the network traffic
    # filter for urls that contain arcgis
    # return the urls
    #
    # 1. revisit the page in a headless browser
    @session.visit(url)

    # wait for the page to load
    sleep 5
    @session.find("body")

    logs = @session.driver.browser.logs.get(:performance)
    logs.each do |log|
      begin
      log_data = JSON.parse(log.message)["message"]
      if log_data["method"] == "Network.responseReceived"
        log_url = log_data["params"]["response"]["url"]

        # strip query params
        candidate_url = URI(log_url)
        formatted_url = candidate_url.scheme + "://" + candidate_url.host + candidate_url.path

        if formatted_url.include?("rest/services") && formatted_url.end_with?("/query")
          candidate_urls << formatted_url
        end
      end
      rescue => e
        puts "Error parsing log: #{e}"
        next
      end
    end

    urls = candidate_urls.uniq
    urls.map { |url| convert_to_geojson_query(url) }
  end

  def convert_to_geojson_query(url)
    if url.include?("MapServer")
      "#{url}?where=1=1&outFields=*&outSR=4326&f=geojson"
    else
      "#{url}?where=1=1&outFields=*&returnGeometry=true&f=geojson"
    end
  end

  def configure_capybara
    Capybara.register_driver :selenium_chrome do |app|
      options = Selenium::WebDriver::Chrome::Options.new

      # Basic Chrome options
      options.add_argument("--disable-gpu")
      options.add_argument("--no-sandbox")
      options.add_argument("--disable-dev-shm-usage")
      options.add_argument("--headless") unless ENV["SHOW_BROWSER"]

      # Enable logging
      options.add_option("goog:loggingPrefs", {
        "performance" => "ALL"
      })

      Capybara::Selenium::Driver.new(
        app,
        browser: :chrome,
        options: options
      )
    end

    Capybara.default_max_wait_time = @timeout
  end

  # Find best fuzzy match
  def self.best_match(key, keys)
    threshold = 0.5 # Lower means stricter matching
    matcher = Amatch::PairDistance.new(key)
    matches = keys.map { |field| [ field, matcher.match(field) ] }

    best_match = matches.min_by { |_, score| score } # Lower score is better
    best_match[1] <= threshold ? best_match[0] : nil # Only accept close matches
  end
end
