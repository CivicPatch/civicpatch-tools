require_relative "../scrapers/data_fetcher"
require_relative "../path_helper"

namespace :scratch do
  desc "Fetch data using Scrapers::DataFetcher"
  task :fetch  do |_t, args|
    url = "https://www.bremertonwa.gov/Directory.aspx?EID=193"
    destination_dir = PathHelper.project_path("./testing")

    begin
      fetcher = Scrapers::DataFetcher.new
      result = fetcher.extract_content(url, destination_dir)
      puts "Successfully fetched data to: #{result}"
    rescue StandardError => e
      puts "Error: #{e.message}"
      puts e.backtrace
      exit 1
    end
  end
end
