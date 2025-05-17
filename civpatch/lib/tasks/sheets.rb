# frozen_string_literal: true

require "googleauth"
require "google/apis/sheets_v4"
require "csv"
require "json"

OOB_URI = "urn:ietf:wg:oauth:2.0:oob"
APPLICATION_NAME = "CSV to Google Sheets"
SCOPE = Google::Apis::SheetsV4::AUTH_SPREADSHEETS

namespace :sheets do
  desc "Send costs to sheets"
  task :send_costs do
    spreadsheet_id = ENV["GOOGLE_SHEETS_SPREADSHEET_ID"]

    if File.exist?(Core::PathHelper.project_path("cost_llms.csv"))
      send_csv_to_sheets_and_clear(spreadsheet_id, "Cost LLMs", Core::PathHelper.project_path("cost_llms.csv"))
    end

    if File.exist?(Core::PathHelper.project_path("cost_search_engine.csv"))
      send_csv_to_sheets_and_clear(spreadsheet_id, "Cost Search Engines",
                                   Core::PathHelper.project_path("cost_search_engine.csv"))
    end
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

    credentials.refresh!

    credentials
  rescue StandardError => e
    puts "Error getting credentials: #{e}"
    nil
  end

  def send_csv_to_sheets_and_clear(spreadsheet_id, sheet_name, csv_file_path) # rubocop:disable Metrics/AbcSize
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

    puts "#{result.updates.updated_cells} cells appended from #{csv_file_path}."
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
