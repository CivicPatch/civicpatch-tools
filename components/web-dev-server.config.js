import proxy from 'koa-proxies';

console.log("api civvieurl: ", process.env.API_CIVICPATCH_ORG_URL)

export default {
  middleware: [
    proxy('/api/api_proxy', {
      target: process.env.API_CIVICPATCH_ORG_URL, // e.g., https://api.civicpatch.org
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/api\/api_proxy/, '/api'),
      logs: true,
      headers: {
        Authorization: process.env.API_CIVICPATCH_ORG_TOKEN,
      },
    }),
  ], 
};

