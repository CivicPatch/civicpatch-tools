require "git"
require "octokit"
require "core/path_helper"

module Services
  class GitHub
    attr_reader :local_repo

    FOLDERS_TO_COPY = %w[config data data_source]
                      .map { |folder| Core::PathHelper.project_path(folder) }

    def initialize
      @client = Octokit::Client.new(access_token: ENV["GITHUB_TOKEN"])

      repo_path = Core::PathHelper.project_path("..")

      @local_repo = Git.open(repo_path)
      raise "Cannot run git operations from the main branch" if @local_repo.current_branch == "main"
    end

    def create_pull_request(context)
      state = context[:state]
      municipality_name = context[:municipality_entry]["name"]

      @local_repo.add(FOLDERS_TO_COPY)
      @local_repo.commit("Add municipal officials for #{municipality_name}, #{state}")
      @local_repo.push("origin", @local_repo.current_branch)

      pull_request_body = "PR opened by the Municipal Officials - Scrape workflow."
      @client.create_pull_request(
        "CivicPatch/civicpatch-tools",
        "main",
        @local_repo.current_branch,
        "Municipality Officials: #{context[:municipality_entry]["name"]}, #{context[:state]}",
        pull_request_body
      )
    end
  end
end
