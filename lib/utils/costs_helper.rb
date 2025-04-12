module Utils
  class CostsHelper
    def self.log_llm_cost(
      request_origin,
      service,
      input_tokens_num,
      output_tokens_num,
      model, notes = ""
    )
      timestamp = Time.now.in_time_zone("America/Los_Angeles").strftime("%Y-%m-%d %H:%M:%S")
      row = [timestamp, request_origin, service, input_tokens_num, output_tokens_num, model, notes].join(",")
      File.write("costs.csv", "#{row}\n", mode: "a")
    end
  end
end
