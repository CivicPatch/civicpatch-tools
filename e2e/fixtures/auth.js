import { randomBytes } from "crypto";
import Redis from "ioredis";

const TOKEN_PREFIX = "session:tok:";
const USER_PREFIX = "session:usr:";
const SESSION_TTL = 3600; // 1 hour

function makeRedis() {
  return new Redis({
    host: process.env.E2E_REDIS_HOST ?? "localhost",
    port: parseInt(process.env.E2E_REDIS_PORT ?? "6379", 10),
  });
}

export async function createTestSession(provider, providerUserId, email, teams) {
  const redis = makeRedis();
  const token = randomBytes(32).toString("hex");
  const csrfNonce = randomBytes(24).toString("hex");
  const expiresAt = Date.now() / 1000 + SESSION_TTL;

  const entry = JSON.stringify({ provider, provider_user_id: providerUserId, email, teams, expires_at: expiresAt });

  await redis.set(`${TOKEN_PREFIX}${token}`, entry, "EX", SESSION_TTL);
  await redis.set(`${USER_PREFIX}${provider}:${providerUserId}`, token, "EX", SESSION_TTL);
  await redis.quit();

  return { token, csrfNonce };
}

export async function injectSessionCookies(context, token, csrfNonce, baseUrl) {
  const url = new URL(baseUrl);
  await context.addCookies([
    {
      name: "token",
      value: token,
      domain: url.hostname,
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
    {
      name: "csrf_token",
      value: csrfNonce,
      domain: url.hostname,
      path: "/",
      httpOnly: false,
      sameSite: "Lax",
    },
  ]);
}

export async function cleanupTestSession(provider, providerUserId) {
  const redis = makeRedis();
  const token = await redis.get(`${USER_PREFIX}${provider}:${providerUserId}`);
  if (token) {
    await redis.del(`${TOKEN_PREFIX}${token}`);
  }
  await redis.del(`${USER_PREFIX}${provider}:${providerUserId}`);
  await redis.quit();
}
