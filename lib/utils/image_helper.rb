module Utils::ImageHelper
  IMAGE_MIME_TO_EXTENSION = {
    "image/jpeg" => "jpg",
    "image/png" => "png",
    "image/gif" => "gif",
    "image/webp" => "webp" # Not supported by GitHub :/
  }.freeze

  IMAGE_EXTENSION_TO_MIME_TYPE = IMAGE_MIME_TO_EXTENSION.invert.freeze

  def self.determine_mime_type(file_path)
    `file --mime-type -b #{file_path}`.strip
  end

  def self.mime_type_to_extension(mime_type)
    IMAGE_MIME_TO_EXTENSION[mime_type]
  end

  def self.get_cdn_url(file_key)
    "https://cdn.civicpatch.org/#{file_key}"
  end
end
