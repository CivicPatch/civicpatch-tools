require "git"
require "octokit"
require "core/path_helper"

module Services
  class GitHub
    attr_reader :local_repo

    FOLDERS_TO_COPY = %w[config data data_source]
                      .map { |folder| Core::PathHelper.project_path(folder) }

    REPO = "CivicPatch/civicpatch-tools".freeze

    def initialize
      @client = Octokit::Client.new(access_token: ENV["GITHUB_TOKEN"])

      repo_path = Core::PathHelper.project_path("..")

      @local_repo = Git.open(repo_path)
      raise "Cannot run git operations from the main branch" if @local_repo.current_branch == "main"
    end

    def update_branch(context)
      state = context[:state]
      municipality_name = context[:municipality_entry]["name"]

      @local_repo.add(FOLDERS_TO_COPY)
      @local_repo.commit("Add municipal officials for #{municipality_name}, #{state}")
      @local_repo.push("origin", @local_repo.current_branch)
    end

    def create_pull_request(context)
      pull_request_body = generate_pr_body(context, has_github_env: ENV["GITHUB_ENV"].present?)
      pr_response = @client.create_pull_request(
        REPO,
        "main",
        @local_repo.current_branch,
        "Municipality Officials: #{context[:municipality_entry]["name"]}, #{context[:state]}",
        pull_request_body
      )

      return unless ENV["GITHUB_ENV"].present?

      @client.add_labels_to_an_issue(
        "CivicPatch/civicpatch-tools",
        pr_response.number,
        [ENV["GITHUB_ENV"]]
      )
    end

    def generate_pr_body(context, has_github_env: false)
      if has_github_env
        branch_name = @local_repo.current_branch
        state = context[:state]
        geoid = context[:municipality_entry]["geoid"]

        city_path = Core::PathHelper.get_data_city_path(state, geoid)
        data_relative_path = city_path[city_path.rindex("data/#{state}")..]
        data_source_relative_path = city_path[city_path.rindex("data_source/#{state}")..]
        config_link = "https://github.com/CivicPatch/open-data/edit/#{branch_name}/#{data_source_relative_path}/config.yml"
        people_link = "https://github.com/CivicPatch/open-data/edit/#{branch_name}/#{data_relative_path}/people.yml"

        <<~PR_BODY
          PR opened by the Municipal Officials - Scrape workflow.
          * people.yml - Make changes [here](#{people_link}) and validation workflows will re-run.
          * config.yml - Make changes [here](#{config_link}) and the entire pipeline will re-run
          (note: if you want the whole pipeline to re-run, do not make changes to people.yml)
        PR_BODY
      else
        "PR opened by the Municipal Officials - Scrape workflow."
      end
    end
  end
end
