# frozen_string_literal: true

require "googleauth"
require "google/apis/sheets_v4"
require "services/google_sheets"

namespace :sheets do
  desc "Send costs to sheets"
  task :send_costs do
    Services::GoogleSheets.send_costs
  end
end
