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

      @local_repo = if Dir.exist?(File.join(repo_path, ".git"))
                      Git.open(repo_path)
                    else
                      Git.init(repo_path)
                    end
      pull_from_remote
    end

    def branch_name(context)
      state = context[:state]
      county = context[:municipality_entry]["counties"].first
      municipality_name = context[:municipality_entry]["name"]
      gnis = context[:municipality_entry]["gnis"]
      random = SecureRandom.hex(8)
      "scrape-#{state}-#{county}-#{municipality_name}-#{gnis}-#{random}"
    end

    def pull_from_remote
      setup_local_repo(@local_repo)

      temp_clone_dir = Core::PathHelper.project_path(File.join("tmp", "remote-clone"))
      FileUtils.mkdir_p(temp_clone_dir) unless Dir.exist?(temp_clone_dir)
      remote_repo = Git.init(temp_clone_dir)
      setup_remote_repo(remote_repo, FOLDERS_TO_COPY)
      copy_remote_to_local(remote_repo, @local_repo, FOLDERS_TO_COPY)

      # FileUtils.rm_rf(temp_clone_dir)
    end

    def create_branch(context)
      branch_name = branch_name(context)

      return unless @local_repo.current_branch != branch_name

      @local_repo.branch(branch_name).checkout
    end

    def create_pull_request(context)
      # state = context[:state]
      # municipality_name = context[:municipality_entry]["name"]

      # @local_repo.add(FOLDERS_TO_COPY)
      # @local_repo.commit("Add municipal officials for #{municipality_name}, #{state}")

      # pull_request_body = %(
      #  PR opened by the Municipal Officials - Scrape workflow.
      # )
      # branch_name = branch_name(context)
      # @client.create_pull_request(
      #  "CivicPatch/civicpatch-tools",
      #  "main",
      #  branch_name,
      #  "Municipality Officials: #{context[:municipality_entry]["name"]}, #{context[:state]}",
      #  pull_request_body
      # )
    end

    private

    def setup_local_repo(local_repo)
      local_repo.add_remote("origin", @repo) if local_repo.remotes.empty?
      local_repo.fetch("origin")
    end

    def setup_remote_repo(remote_repo, folders)
      remote_repo.config("core.sparseCheckout", "true")
      sparse_checkout_file = File.join(remote_repo.dir.path, ".git", "info", "sparse-checkout")
      File.write(sparse_checkout_file, folders.join("\n"))

      remote_repo.add_remote("origin", @repo) if remote_repo.remotes.empty?
      remote_repo.fetch("origin")
      remote_repo.branch("main").checkout
    end

    def copy_remote_to_local(remote_repo, local_repo, folders_to_copy)
      folders_to_copy.each do |folder|
        source_folder = File.join(remote_repo.dir.path, folder)
        destination_folder = File.join(local_repo.dir.path)

        next unless Dir.exist?(source_folder)

        FileUtils.rm_rf(destination_folder) if Dir.exist?(destination_folder)
        FileUtils.mkdir_p(destination_folder) unless Dir.exist?(destination_folder)
        FileUtils.cp_r(source_folder, destination_folder) if Dir.exist?(source_folder)
      end
    end
  end
end
