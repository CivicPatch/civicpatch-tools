# frozen_string_literal: true

require "aws-sdk-s3"

module Services
  class Spaces
    ENDPOINT = ENV["CLOUDFLARE_R2_ENDPOINT"]
    ACCESS_KEY_ID = ENV["CLOUDFLARE_R2_ACCESS_KEY_ID"]
    SECRET_KEY = ENV["CLOUDFLARE_R2_SECRET_KEY"]

    def self.client
      @client ||= Aws::S3::Client.new(
        access_key_id: ACCESS_KEY_ID,
        secret_access_key: SECRET_KEY,
        endpoint: ENDPOINT,
        region: "auto"
      )
    end

    def self.put_object(key, image_path, content_type)
      client.put_object({
                          bucket: "civicpatch",
                          key: "open-data/#{key}",
                          body: File.read(image_path),
                          acl: "public-read",
                          content_type: content_type
                        })
    end
  end
end
