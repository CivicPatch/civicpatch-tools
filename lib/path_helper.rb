module PathHelper
  def self.project_path(relative_path)
    File.expand_path(relative_path, Dir.pwd)
  end
end
