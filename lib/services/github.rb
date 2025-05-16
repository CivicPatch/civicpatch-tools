require "git"
require "octokit"
require_relative "../path_helper"

module Services
  class GitHub
    attr_reader :local_repo

    def initialize(develop: false)
      @client = Octokit::Client.new(access_token: ENV["GITHUB_TOKEN"])
      @repo = "https://#{ENV["GITHUB_USERNAME"]}:#{ENV["GITHUB_TOKEN"]}@github.com/CivicPatch/open-data.git"
      @local_repo = develop ? Git.open(PathHelper.project_path("")) : Git.init
      return if develop

      @local_repo.config("core.sparseCheckout", "true")
      @local_repo.add_remote("origin", @repo)
      @local_repo.fetch("origin")
      @local_repo.checkout("main")
    end

    def pull_and_create_branch(municipality_context)
      state = municipality_context[:state]
      county = municipality_context[:municipality_entry]["counties"].first
      municipality_name = municipality_context[:municipality_entry]["name"]
      gnis = municipality_context[:municipality_entry]["gnis"]
      random = SecureRandom.hex(8)
      branch_name = "scrape-#{state}-#{county}-#{municipality_name}-#{gnis}-#{random}"

      @local_repo.checkout("main", force: true)
      @local_repo.pull
      @local_repo.branch(branch_name)
    end

    def create_pull_request(municipality_context)
      state = municipality_context[:state]
      municipality_name = municipality_context[:municipality_entry]["name"]

      @local_repo.add(%w[data data_source])
      @local_repo.commit("Add municipal officials for #{municipality_name}, #{state}")

      pull_request_body = %(
        PR opened by the Municipal Officials - Scrape workflow.
      )
      @client.create_pull_request(
        "CivicPatch/open-data",
        "main",
        branch_name, # TODO: Add head
        "Municipality Officials: #{municipality_context[:municipality_entry]["name"]}, #{municipality_context[:state]}",
        pull_request_body
      )
    end
  end
end
