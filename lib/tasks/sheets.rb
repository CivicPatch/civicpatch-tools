require "googleauth"
require "google/apis/sheets_v4"
require "csv"
require "json"

namespace :sheets do
  desc "Send costs to sheets"
  task :send_costs do
    OOB_URI = "urn:ietf:wg:oauth:2.0:oob".freeze
    APPLICATION_NAME = "CSV to Google Sheets".freeze
    SCOPE = Google::Apis::SheetsV4::AUTH_SPREADSHEETS
    spreadsheet_id = ENV["GOOGLE_SHEETS_SPREADSHEET_ID"] # Spreadsheet ID from environment variable
    sheet_name = "Costs"
    csv_file_path = PathHelper.project_path("costs.csv")

    send_csv_to_sheets_and_clear(spreadsheet_id, sheet_name, csv_file_path)
  end

  private

  def authorize
    client_id = ENV["GOOGLE_SHEETS_CLIENT_ID"]
    client_secret = ENV["GOOGLE_SHEETS_CLIENT_SECRET"]
    refresh_token = ENV["GOOGLE_SHEETS_REFRESH_TOKEN"]

    credentials = Google::Auth::UserRefreshCredentials.new(
      client_id: client_id,
      client_secret: client_secret,
      scope: SCOPE,
      refresh_token: refresh_token
    )

    if credentials.refresh_token.nil?
      url = credentials.authorization_uri(base_url: OOB_URI)
      puts "Open the following URL in the browser and enter the " \
           "resulting code after authorization:\n" + url
      code = gets.chomp
      credentials.get_credentials_from_code(user_code: code, base_url: OOB_URI)
      puts "Set GOOGLE_SHEETS_REFRESH_TOKEN to : #{credentials.refresh_token}"
    else
      credentials.refresh!
    end
    credentials
  rescue Google::Auth::CredentialsError => e
    puts "Error getting credentials: #{e}"
    nil
  end

  def send_csv_to_sheets_and_clear(spreadsheet_id, sheet_name, csv_file_path)
    service = Google::Apis::SheetsV4::SheetsService.new
    service.client_options.application_name = APPLICATION_NAME
    service.authorization = authorize

    return unless service.authorization

    values = []
    CSV.foreach(csv_file_path, encoding: "utf-8") do |row|
      values << row
    end

    range_name = "#{sheet_name}!A1" # start at A1, but use APPEND
    body = Google::Apis::SheetsV4::ValueRange.new(values: values)
    result = service.append_spreadsheet_value(spreadsheet_id, range_name, body, value_input_option: "RAW",
                                                                                insert_data_option: "INSERT_ROWS")

    puts "#{result.updates.updated_cells} cells appended."
    File.open(csv_file_path, "w") { |file| file.truncate(0) } # Clears the csv
    result
  rescue Google::Apis::ClientError => e
    puts "An error occurred: #{e}"
    nil
  rescue Errno::ENOENT
    puts "Error: File not found at #{csv_file_path}"
    nil
  end
end
