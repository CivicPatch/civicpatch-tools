import express from 'express';
import { createProxyMiddleware } from 'http-proxy-middleware';

export default {
  rootDir: '.',
  watch: true,
  open: '/index.dev.html',
  nodeResolve: true,
  app: (app) => {
    // Proxy /api/api_proxy/* → actual API with Authorization header
    app.use(
      '/api/api_proxy',
      createProxyMiddleware({
        target: process.env.API_CIVICPATCH_ORG_URL,
        changeOrigin: true,
        pathRewrite: {
          '^/api/api_proxy': '/api', // map /api/api_proxy/* → /api/*
        },
        onProxyReq: (proxyReq, req) => {
          // Inject authorization header from env var
          if (!process.env.API_CIVICPATCH_ORG_TOKEN) {
            throw new Error('Missing API_CIVICPATCH_ORG_TOKEN');
          }
          proxyReq.setHeader(
            'Authorization',
            process.env.API_CIVICPATCH_ORG_TOKEN
          );
        },
        onProxyRes: (proxyRes, req, res) => {
          // Optional: modify response headers if needed
        },
      })
    );
  },
  port: 9001,
};

