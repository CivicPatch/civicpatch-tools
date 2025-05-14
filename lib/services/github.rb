require "git"
require "octokit"
require "path_helper"

module Services
  class GitHub
    def initialize
      @client = Octokit::Client.new(access_token: ENV["GITHUB_TOKEN"])
      @repo = "CivicPatch/open-data"
      @local_repo = Git.open(PathHelper.project_path(""))
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

      @local_repo.add(all: true)
      @local_repo.commit("Add municipal officials for #{municipality_name}, #{state}")

      pull_request_body = %(
        PR opened by the Municipal Officials - Scrape workflow.
      )
      @client.create_pull_request(
        "CivicPatch/open-data",
        "main",
        "head", # TODO: Add head
        "Municipality Officials: #{municipality_context[:municipality_entry]["name"]}, #{municipality_context[:state]}",
        pull_request_body
      )
    end
  end
end
