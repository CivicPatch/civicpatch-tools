module Utils
  module DateHelper
    def self.format_date(date_string)
      # Date is "2025", update to 2025-12-31
      return "#{date_string}-12-31" if date_string.to_s.match?(/^\d{4}$/)

      # If date === 2025-12, update to 2025-12-31
      return unless date_string.to_s.match?(/^\d{4}-\d{2}$/)

      "#{date_string}-31"

      # If date === 2025-12-31, return 2025-12-31
    end

    def self.get_last_day_of_month(year_month_string)
      return nil unless year_month_string.to_s.match?(/^\d{4}-\d{2}$/)

      year, month = year_month_string.split("-").map(&:to_i)

      return nil unless month >= 1 && month <= 12

      begin
        last_day = Date.new(year, month, -1)
        last_day.strftime("%Y-%m-%d")
      rescue ArgumentError
        nil
      end
    end
  end
end
