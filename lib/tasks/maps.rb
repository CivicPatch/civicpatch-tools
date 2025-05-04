# frozen_string_literal: true

namespace :maps do
  desc "Download the maps for the given state"
  task :d_mun, [:state] do |_task, args|
    state = args[:state]

    Services::Census.download_municipalities(state)
  end
end
