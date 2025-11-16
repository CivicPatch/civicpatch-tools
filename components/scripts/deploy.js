// scripts/deploy-r2.js
import fs from 'fs';
import path from 'path';
import { S3Client, PutObjectCommand } from '@aws-sdk/client-s3';

const BUCKET = "civicpatch-components";
const REGION = 'auto';
const ENDPOINT = process.env.STORAGE_ENDPOINT;

const client = new S3Client({
  region: REGION,
  endpoint: ENDPOINT,
  credentials: {
    accessKeyId: process.env.STORAGE_ACCESS_KEY_ID,
    secretAccessKey: process.env.STORAGE_SECRET_ACCESS_KEY
  }
});

async function uploadFolder(folderPath, prefix = '') {
  const files = fs.readdirSync(folderPath);
  for (const file of files) {
    const filePath = path.join(folderPath, file);
    const stat = fs.statSync(filePath);
    if (stat.isDirectory()) {
      console.log("starting upload...")
      await uploadFolder(filePath, path.join(prefix, file));
      console.log("finished upload")
    } else {
      const body = fs.readFileSync(filePath);
      await client.send(new PutObjectCommand({
        Bucket: BUCKET,
        Key: path.join(prefix, file),
        Body: body
      }));
      console.log(`Uploaded ${path.join(prefix, file)}`);
    }
  }
}

(async () => {
  const distFolder = path.join(process.cwd(), 'dist'); // your build folder
  console.log('Uploading from:', path.join(process.cwd(), 'dist'));

  await uploadFolder(distFolder);
})();

