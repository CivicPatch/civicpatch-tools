require "googleauth"
require "google/apis/sheets_v4"
require "csv"
require "json"

OOB_URI = "urn:ietf:wg:oauth:2.0:oob".freeze
APPLICATION_NAME = "CSV to Google Sheets".freeze
SCOPE = Google::Apis::SheetsV4::AUTH_SPREADSHEETS

module Services
  class GoogleSheets
    def self.enabled?
      puts "Checking if Google Sheets integration is enabled..."
      enabled = ENV["GOOGLE_SHEETS_CLIENT_ID"].present? &&
                ENV["GOOGLE_SHEETS_CLIENT_SECRET"].present? &&
                ENV["GOOGLE_SHEETS_REFRESH_TOKEN"].present? &&
                ENV["GOOGLE_SHEETS_SPREADSHEET_ID"].present?
      puts "Google Sheets integration enabled: #{enabled}"
      enabled
    end

    def self.send_costs
      puts "Starting to send costs to Google Sheets..."
      spreadsheet_id = ENV["GOOGLE_SHEETS_SPREADSHEET_ID"]
      puts "Spreadsheet ID: #{spreadsheet_id}"

      service = setup_client
      if service.nil?
        puts "Error setting up Google Sheets client, skipping sending costs..."
        return
      end

      cost_file_paths = { "Cost LLMs" => Core::PathHelper.project_path("cost_llms.csv"), 
                          "Cost Search Engines" => Core::PathHelper.project_path("cost_search_engine.csv") }

      cost_file_paths.each do |sheet_name, csv_file_path|
        if !File.exist?(csv_file_path)
          puts "CSV file not found for sheet: #{sheet_name}, path: #{csv_file_path}"
          next
        end

        puts "Sending data to sheet: #{sheet_name}, from file: #{csv_file_path}"
        send_cost_to_sheets(service, spreadsheet_id, sheet_name, csv_file_path)
      end
    end

    def self.send_cost_to_sheets(service, spreadsheet_id, sheet_name, csv_file_path)
      values = []
      CSV.foreach(csv_file_path, encoding: "utf-8") do |row|
        values << row
      end

      range_name = "#{sheet_name}!A1" # start at A1, but use APPEND
      body = Google::Apis::SheetsV4::ValueRange.new(values: values)

      begin
        result = service.append_spreadsheet_value(spreadsheet_id, range_name, body, value_input_option: "RAW",
                                                                                      insert_data_option: "INSERT_ROWS")
        puts "#{result.updates.updated_cells} cells appended from #{csv_file_path}."
        File.open(csv_file_path, "w") { |file| file.truncate(0) } # Clears the csv
        result
      rescue StandardError => e
        puts "Error appending data to Google Sheets: #{e.message}"
        puts e.backtrace
      end
    end

    def self.setup_client
      service = Google::Apis::SheetsV4::SheetsService.new
      service.client_options.application_name = APPLICATION_NAME
      service.authorization = authorize

      if service.authorization.nil?
        puts "Authorization failed for Google Sheets client."
        return nil
      end

      puts "Google Sheets client setup complete."
      service
    end

    def self.authorize
      puts "Authorizing Google Sheets client..."
      client_id = ENV["GOOGLE_SHEETS_CLIENT_ID"]
      client_secret = ENV["GOOGLE_SHEETS_CLIENT_SECRET"]
      refresh_token = ENV["GOOGLE_SHEETS_REFRESH_TOKEN"]

      if client_id.nil? || client_secret.nil? || refresh_token.nil?
        puts "Missing Google Sheets credentials in environment variables."
        return nil
      end

      credentials = Google::Auth::UserRefreshCredentials.new(
        client_id: client_id,
        client_secret: client_secret,
        scope: SCOPE,
        refresh_token: refresh_token
      )

      begin
        credentials.refresh!
        puts "Google Sheets credentials refreshed successfully."
      rescue StandardError => e
        puts "Error refreshing Google Sheets credentials: #{e.message}"
        puts e.backtrace
        return nil
      end

      credentials
    end
  end
end
