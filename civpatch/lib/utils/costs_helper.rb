# frozen_string_literal: true

module Utils
  class CostsHelper
    # Define costs per token (adjust as needed based on current pricing)
    MODEL_COSTS = {
      # $0.40/1M input, $1.60/1M output
      "gpt-4.1-mini" => { input: 0.0000004, output: 0.0000016 },
      # $0.15/1M input, $0.60/1M output, with_search = $35 per 1000 requests
      "gemini-2.5-flash-preview-04-17" => { input: 0.00000015, output: 0.0000006, with_search: 0.035 },
      "gemini-2.5-flash-preview-05-20" => { input: 0.00000015, output: 0.0000006, with_search: 0.035 },
      "gemini-2.0-flash" => { input: 0.00000010, output: 0.0000004, with_search: 0.035 }
      # Add other models and their costs here
    }.freeze

    def self.timestamp
      Time.now.in_time_zone("America/Los_Angeles").strftime("%Y-%m-%d")
    end

    # Max 10K requests per day -- 3333 cities hard limit
    def self.log_search_engine_call(state, municipality_name, search_engine)
      # $5 per 1000 requests
      cost = if search_engine == "google"
               0.005
             elsif search_engine == "brave"
               0.003
             else
               0.000
             end
      row = [timestamp, state, municipality_name, search_engine, cost].join(",")
      File.write("cost_search_engine.csv", "#{row}\n", mode: "a")
    end

    def self.log_llm_cost( # rubocop:disable Metrics/ParameterLists
      state,
      municipality_name,
      service,
      input_tokens_num,
      output_tokens_num,
      model,
      notes = "",
      with_search: false
    )
      cost = 0.0 # Default cost
      model_rates = MODEL_COSTS[model]

      if model_rates
        cost = (input_tokens_num * model_rates[:input]) + (output_tokens_num * model_rates[:output])
        cost += model_rates[:with_search] if with_search
      else
        puts "Warning: Cost rates not found for model '#{model}'. Logging cost as 0."
      end

      # Ensure all values are present and properly quoted if they might contain commas
      row_elements = [
        timestamp,
        state,
        municipality_name,
        service,
        input_tokens_num,
        output_tokens_num,
        with_search,
        model,
        cost.round(6), # Add calculated cost, rounded
        notes # Ensure notes are properly handled if they contain commas
      ]
      # Simple CSV join - consider using a proper CSV library for robustness if notes can have commas
      row = row_elements.join(",")
      File.write("cost_llms.csv", "#{row}\n", mode: "a")
    end
  end
end
