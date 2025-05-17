require "git"
require "octokit"
require "core/path_helper"

module Services
  class GitHub
    attr_reader :local_repo

    FOLDERS_TO_COPY = ["civpatch/config", "civpatch/data", "civpatch/data_source"].freeze

    def initialize
      @client = Octokit::Client.new(access_token: ENV["GITHUB_TOKEN"])
      @repo = "https://#{ENV["GITHUB_USERNAME"]}:#{ENV["GITHUB_TOKEN"]}@github.com/CivicPatch/civicpatch-tools.git"

      repo_path = Core::PathHelper.project_path("..")

      @local_repo = Git.open(repo_path)
      raise "Cannot run git operations from the main branch" if @local_repo.current_branch == "main"
    end

    def create_pull_request(context)
      state = context[:state]
      municipality_name = context[:municipality_entry]["name"]

      @local_repo.add(FOLDERS_TO_COPY)
      @local_repo.commit("Add municipal officials for #{municipality_name}, #{state}")

      pull_request_body = %(
       PR opened by the Municipal Officials - Scrape workflow.
      )
      branch_name = @local_repo.current_branch
      @client.create_pull_request(
        "CivicPatch/civicpatch-tools",
        "main",
        branch_name,
        "Municipality Officials: #{context[:municipality_entry]["name"]}, #{context[:state]}",
        pull_request_body
      )
    end
  end
end
