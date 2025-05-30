module Utils
  module RetryHelper
    BASE_SLEEP = 2

    def self.with_retry(max_retries)
      retry_attempts = 0

      begin
        yield
      rescue StandardError => e
        if retry_attempts < max_retries
          sleep_time = BASE_SLEEP**retry_attempts + rand(0..1)
          sleep sleep_time
          retry_attempts += 1

          puts "#{e.message} - Retrying in #{sleep_time} seconds... (Attempt ##{retry_attempts + 1})"
          retry
        end

        raise e
      end
    end
  end
end
