require "googleauth"
require "google/apis/sheets_v4"
require "csv"
require "json"

OOB_URI = "urn:ietf:wg:oauth:2.0:oob".freeze
APPLICATION_NAME = "CSV to Google Sheets".freeze
SCOPE = Google::Apis::SheetsV4::AUTH_SPREADSHEETS

module Services
  class GoogleSheets
    def self.send_costs
      spreadsheet_id = ENV["GOOGLE_SHEETS_SPREADSHEET_ID"]
      service = setup_client

      if service.nil?
        puts "Error setting up Google Sheets client, skipping sending costs..."
        return
      end

      cost_file_paths = { "Cost LLMs" => Core::PathHelper.project_path("cost_llms.csv"),
                          "Cost Search Engines" => Core::PathHelper.project_path("cost_search_engine.csv") }

      cost_file_paths.each do |sheet_name, csv_file_path|
        send_cost_to_sheets(spreadsheet_id, sheet_name, csv_file_path)
      end
    end

    def self.send_cost_to_sheets(spreadsheet_id, sheet_name, csv_file_path)
      values = []
      CSV.foreach(csv_file_path, encoding: "utf-8") do |row|
        values << row
      end

      range_name = "#{sheet_name}!A1" # start at A1, but use APPEND
      body = Google::Apis::SheetsV4::ValueRange.new(values: values)
      result = service.append_spreadsheet_value(spreadsheet_id, range_name, body, value_input_option: "RAW",
                                                                                  insert_data_option: "INSERT_ROWS")

      puts "#{result.updates.updated_cells} cells appended from #{csv_file_path}."
      File.open(csv_file_path, "w") { |file| file.truncate(0) } # Clears the csv
      result
    end

    def self.setup_client
      service = Google::Apis::SheetsV4::SheetsService.new
      service.client_options.application_name = APPLICATION_NAME
      service.authorization = authorize

      nil unless service.authorization
    end

    def self.authorize
      client_id = ENV["GOOGLE_SHEETS_CLIENT_ID"]
      client_secret = ENV["GOOGLE_SHEETS_CLIENT_SECRET"]
      refresh_token = ENV["GOOGLE_SHEETS_REFRESH_TOKEN"]

      credentials = Google::Auth::UserRefreshCredentials.new(
        client_id: client_id,
        client_secret: client_secret,
        scope: SCOPE,
        refresh_token: refresh_token
      )

      credentials.refresh!

      credentials
    end
  end
end
