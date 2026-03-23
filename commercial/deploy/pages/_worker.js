/**
 * English Coach cloud activation + AI proxy worker.
 *
 * Required secrets:
 *   CLIENT_TOKEN         buyer-side activation token for /activate and /verify
 *   ADMIN_TOKEN          seller-side token for /register, /revoke and /inspect
 *   CLOUD_API_KEY        upstream DeepSeek API key (never leaves the backend)
 *
 * Recommended extra secret:
 *   SESSION_TOKEN_SECRET dedicated signing secret for per-license proxy tokens
 *
 * Optional config vars/secrets:
 *   ALLOWED_MODELS              comma-separated allowlist, default: deepseek-chat
 *   MAX_PROXY_BODY_BYTES        default: 65536
 *   MAX_PROXY_MESSAGES          default: 32
 *   MAX_PROXY_MESSAGE_CHARS     default: 12000
 *   MAX_PROXY_TOTAL_CHARS       default: 40000
 *   MAX_PROXY_MAX_TOKENS        default: 2000
 *   BURST_REQUEST_LIMIT         default: 20
 *   BURST_WINDOW_SECONDS        default: 60
 *   DAILY_REQUEST_LIMIT         default: 200
 *   DAILY_INPUT_CHARS_LIMIT     default: 200000
 *   AI_BASE_URL                 default: https://api.deepseek.com/v1
 *
 * KV namespace:
 *   LICENSE_KV
 */

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, X-Worker-Token, Authorization",
};

const DEFAULT_AI_BASE_URL = "https://api.deepseek.com/v1";
const DEFAULT_MODEL = "deepseek-chat";
const LICENSE_TTL_SECONDS = 3 * 86400;
const MIN_BURST_TTL_SECONDS = 180;

export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS });
    }

    const url = new URL(request.url);
    if (request.method !== "POST") {
      return json({ error: "Not found" }, 404);
    }

    switch (url.pathname) {
      case "/register":
        return handleRegister(request, env);
      case "/activate":
        return handleActivate(request, env);
      case "/verify":
        return handleVerify(request, env);
      case "/revoke":
        return handleRevoke(request, env);
      case "/inspect":
        return handleInspect(request, env);
      case "/v1/chat/completions":
        return handleChatCompletions(request, env);
      default:
        return json({ error: "Not found" }, 404);
    }
  },
};

function json(data, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...CORS, ...extraHeaders },
  });
}

async function hmacHex(secret, text) {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"]
  );
  const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(text));
  return Array.from(new Uint8Array(sig)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function envInt(env, name, fallback, min, max) {
  const raw = String(env[name] ?? "").trim();
  if (!raw) {
    return fallback;
  }
  const parsed = parseInt(raw, 10);
  if (!Number.isFinite(parsed)) {
    return fallback;
  }
  return Math.min(Math.max(parsed, min), max);
}

function proxyConfig(env) {
  const models = String(env.ALLOWED_MODELS || DEFAULT_MODEL)
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return {
    allowedModels: new Set(models.length ? models : [DEFAULT_MODEL]),
    maxBodyBytes: envInt(env, "MAX_PROXY_BODY_BYTES", 65536, 4096, 262144),
    maxMessages: envInt(env, "MAX_PROXY_MESSAGES", 32, 1, 128),
    maxMessageChars: envInt(env, "MAX_PROXY_MESSAGE_CHARS", 12000, 100, 50000),
    maxTotalChars: envInt(env, "MAX_PROXY_TOTAL_CHARS", 40000, 500, 200000),
    maxTokens: envInt(env, "MAX_PROXY_MAX_TOKENS", 2000, 1, 8192),
    burstRequestLimit: envInt(env, "BURST_REQUEST_LIMIT", 20, 1, 500),
    burstWindowSeconds: envInt(env, "BURST_WINDOW_SECONDS", 60, 10, 3600),
    dailyRequestLimit: envInt(env, "DAILY_REQUEST_LIMIT", 200, 1, 100000),
    dailyInputCharsLimit: envInt(env, "DAILY_INPUT_CHARS_LIMIT", 200000, 1000, 10000000),
  };
}

function publicProxyConfig(cfg) {
  return {
    allowed_models: Array.from(cfg.allowedModels),
    max_body_bytes: cfg.maxBodyBytes,
    max_messages: cfg.maxMessages,
    max_message_chars: cfg.maxMessageChars,
    max_total_chars: cfg.maxTotalChars,
    max_max_tokens: cfg.maxTokens,
    burst_request_limit: cfg.burstRequestLimit,
    burst_window_seconds: cfg.burstWindowSeconds,
    daily_request_limit: cfg.dailyRequestLimit,
    daily_input_chars_limit: cfg.dailyInputCharsLimit,
  };
}

function readToken(request) {
  return request.headers.get("X-Worker-Token") || "";
}

function readBearerToken(request) {
  const auth = request.headers.get("Authorization") || "";
  return auth.startsWith("Bearer ") ? auth.slice(7).trim() : "";
}

function validateClientToken(request, env) {
  const token = readToken(request);
  return token && (token === env.CLIENT_TOKEN || token === env.WORKER_SECRET);
}

function validateAdminToken(request, env) {
  const token = readToken(request);
  return token && (token === env.ADMIN_TOKEN || token === env.WORKER_SECRET);
}

function normalizeKey(key) {
  return key.trim().toUpperCase().replace(/-/g, "");
}

function displayKey(key) {
  const norm = normalizeKey(key);
  return `${norm.slice(0, 4)}-${norm.slice(4, 8)}-${norm.slice(8, 12)}-${norm.slice(12, 16)}`;
}

function isValidKeyFormat(key) {
  return /^[0-9A-F]{16}$/.test(normalizeKey(key));
}

function timingSafeEqual(a, b) {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) {
    return false;
  }
  let diff = 0;
  for (let i = 0; i < a.length; i += 1) {
    diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return diff === 0;
}

function base64UrlEncode(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (const byte of bytes) {
    binary += String.fromCharCode(byte);
  }
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function base64UrlDecode(text) {
  const padLen = (4 - (text.length % 4)) % 4;
  const padded = text + "=".repeat(padLen);
  const base64 = padded.replace(/-/g, "+").replace(/_/g, "/");
  const binary = atob(base64);
  const bytes = Uint8Array.from(binary, (char) => char.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

function sessionTokenSecret(env) {
  return env.SESSION_TOKEN_SECRET || env.LICENSE_SECRET || env.ADMIN_TOKEN || env.WORKER_SECRET || "";
}

async function createSessionToken(payload, env) {
  const secret = sessionTokenSecret(env);
  if (!secret) {
    throw new Error("Missing SESSION_TOKEN_SECRET");
  }
  const body = base64UrlEncode(JSON.stringify(payload));
  const sig = await hmacHex(secret, body);
  return `${body}.${sig}`;
}

async function verifySessionToken(token, env) {
  if (!token) {
    return { ok: false, error: "Missing session token" };
  }
  const dot = token.indexOf(".");
  if (dot <= 0) {
    return { ok: false, error: "Invalid session token" };
  }

  const body = token.slice(0, dot);
  const sig = token.slice(dot + 1);
  const secret = sessionTokenSecret(env);
  if (!secret) {
    return { ok: false, error: "Server misconfigured" };
  }

  const expected = await hmacHex(secret, body);
  if (!timingSafeEqual(sig, expected)) {
    return { ok: false, error: "Session token signature mismatch" };
  }

  let payload;
  try {
    payload = JSON.parse(base64UrlDecode(body));
  } catch {
    return { ok: false, error: "Session token payload invalid" };
  }

  if (!payload || payload.v !== 1 || !payload.key || !payload.machine_id) {
    return { ok: false, error: "Session token payload incomplete" };
  }
  if (!isValidKeyFormat(payload.key)) {
    return { ok: false, error: "Session token key invalid" };
  }

  return { ok: true, payload };
}

async function readJsonLimited(request, maxBytes) {
  const text = await request.text();
  const size = new TextEncoder().encode(text).length;
  if (size === 0) {
    return { ok: false, status: 400, error: "Empty body" };
  }
  if (size > maxBytes) {
    return { ok: false, status: 413, error: `Request body too large (${size} bytes)` };
  }
  try {
    return { ok: true, data: JSON.parse(text), size };
  } catch {
    return { ok: false, status: 400, error: "Invalid JSON" };
  }
}

async function loadJsonValue(env, key, fallback) {
  const raw = await env.LICENSE_KV.get(key);
  if (!raw) {
    return fallback;
  }
  try {
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

async function putJsonValue(env, key, value, ttlSeconds) {
  await env.LICENSE_KV.put(key, JSON.stringify(value), { expirationTtl: ttlSeconds });
}

async function loadLicenseRecord(key, env) {
  return loadJsonValue(env, normalizeKey(key), null);
}

function computeDaysLeft(record) {
  const now = Math.floor(Date.now() / 1000);
  const expireTs = record.activate_ts + record.days * 86400;
  return Math.floor((expireTs - now) / 86400);
}

function todayStamp(now) {
  return new Date(now * 1000).toISOString().slice(0, 10);
}

function usageCounterKey(key, date) {
  return `usage:${normalizeKey(key)}:${date}`;
}

function burstCounterKey(key, machineId, windowSeconds, bucket) {
  return `burst:${normalizeKey(key)}:${machineId}:${windowSeconds}:${bucket}`;
}

async function recordBlockedAttempt(env, key, date, reason) {
  const counterKey = usageCounterKey(key, date);
  const current = await loadJsonValue(env, counterKey, {
    requests: 0,
    input_chars: 0,
    output_tokens: 0,
    blocked: 0,
    last_seen_ts: 0,
    last_block_reason: "",
  });
  current.blocked += 1;
  current.last_seen_ts = Math.floor(Date.now() / 1000);
  current.last_block_reason = reason;
  await putJsonValue(env, counterKey, current, LICENSE_TTL_SECONDS);
}

async function reserveQuota(env, key, machineId, inputChars, cfg) {
  const now = Math.floor(Date.now() / 1000);
  const date = todayStamp(now);
  const usageKey = usageCounterKey(key, date);
  const burstKey = burstCounterKey(
    key,
    machineId,
    cfg.burstWindowSeconds,
    Math.floor(now / cfg.burstWindowSeconds)
  );
  const usage = await loadJsonValue(env, usageKey, {
    requests: 0,
    input_chars: 0,
    output_tokens: 0,
    blocked: 0,
    last_seen_ts: 0,
    last_block_reason: "",
  });
  const burst = await loadJsonValue(env, burstKey, {
    requests: 0,
    last_seen_ts: 0,
  });

  if (usage.requests >= cfg.dailyRequestLimit) {
    await recordBlockedAttempt(env, key, date, "daily_request_limit");
    return {
      ok: false,
      status: 429,
      error: `已超过今日请求上限（${cfg.dailyRequestLimit}）`,
      retryAfter: "86400",
    };
  }
  if (usage.input_chars + inputChars > cfg.dailyInputCharsLimit) {
    await recordBlockedAttempt(env, key, date, "daily_input_chars_limit");
    return {
      ok: false,
      status: 429,
      error: `已超过今日文本额度（${cfg.dailyInputCharsLimit} chars）`,
      retryAfter: "86400",
    };
  }
  if (burst.requests >= cfg.burstRequestLimit) {
    await recordBlockedAttempt(env, key, date, "burst_request_limit");
    return {
      ok: false,
      status: 429,
      error: `请求过于频繁，请稍后再试（${cfg.burstWindowSeconds}s 窗口）`,
      retryAfter: String(cfg.burstWindowSeconds),
    };
  }

  usage.requests += 1;
  usage.input_chars += inputChars;
  usage.last_seen_ts = now;
  burst.requests += 1;
  burst.last_seen_ts = now;

  await Promise.all([
    putJsonValue(env, usageKey, usage, LICENSE_TTL_SECONDS),
    putJsonValue(
      env,
      burstKey,
      burst,
      Math.max(MIN_BURST_TTL_SECONDS, cfg.burstWindowSeconds * 3)
    ),
  ]);

  return { ok: true, usageKey, usage, now, date };
}

async function finalizeQuota(env, usageKey, usage, now, upstreamResponseText) {
  let outputTokens = 0;
  try {
    const parsed = JSON.parse(upstreamResponseText);
    const usageInfo = parsed && typeof parsed === "object" ? parsed.usage || {} : {};
    outputTokens = parseInt(
      usageInfo.completion_tokens || usageInfo.output_tokens || 0,
      10
    );
    if (!Number.isFinite(outputTokens) || outputTokens < 0) {
      outputTokens = 0;
    }
  } catch {
    outputTokens = 0;
  }
  usage.output_tokens = (usage.output_tokens || 0) + outputTokens;
  usage.last_seen_ts = now;
  await putJsonValue(env, usageKey, usage, LICENSE_TTL_SECONDS);
}

function validateProxyPayload(body, cfg) {
  if (!body || typeof body !== "object" || Array.isArray(body)) {
    return { ok: false, status: 400, error: "Invalid request body" };
  }

  const model = String(body.model || DEFAULT_MODEL).trim();
  if (!cfg.allowedModels.has(model)) {
    return { ok: false, status: 400, error: `Model not allowed: ${model}` };
  }

  if (body.stream === true) {
    return { ok: false, status: 400, error: "Streaming is not supported by this proxy" };
  }

  const messages = body.messages;
  if (!Array.isArray(messages) || messages.length === 0) {
    return { ok: false, status: 400, error: "messages must be a non-empty array" };
  }
  if (messages.length > cfg.maxMessages) {
    return { ok: false, status: 400, error: `Too many messages (max ${cfg.maxMessages})` };
  }

  let totalChars = 0;
  const sanitizedMessages = [];
  for (const msg of messages) {
    if (!msg || typeof msg !== "object" || Array.isArray(msg)) {
      return { ok: false, status: 400, error: "Invalid message item" };
    }
    const role = String(msg.role || "").trim();
    if (!["system", "user", "assistant"].includes(role)) {
      return { ok: false, status: 400, error: `Unsupported role: ${role}` };
    }
    if (typeof msg.content !== "string") {
      return { ok: false, status: 400, error: "Only string message content is supported" };
    }
    const content = msg.content.trim();
    if (!content) {
      return { ok: false, status: 400, error: "Empty message content is not allowed" };
    }
    if (content.length > cfg.maxMessageChars) {
      return {
        ok: false,
        status: 400,
        error: `Message too long (max ${cfg.maxMessageChars} chars per message)`,
      };
    }
    totalChars += content.length;
    if (totalChars > cfg.maxTotalChars) {
      return {
        ok: false,
        status: 400,
        error: `Total message content too long (max ${cfg.maxTotalChars} chars)`,
      };
    }
    sanitizedMessages.push({ role, content });
  }

  const maxTokensRaw = body.max_tokens == null ? cfg.maxTokens : parseInt(body.max_tokens, 10);
  if (!Number.isFinite(maxTokensRaw) || maxTokensRaw <= 0 || maxTokensRaw > cfg.maxTokens) {
    return {
      ok: false,
      status: 400,
      error: `max_tokens must be between 1 and ${cfg.maxTokens}`,
    };
  }

  const payload = {
    model,
    messages: sanitizedMessages,
    max_tokens: maxTokensRaw,
  };

  for (const optional of ["temperature", "top_p", "presence_penalty", "frequency_penalty", "stop"]) {
    if (body[optional] !== undefined) {
      payload[optional] = body[optional];
    }
  }

  return { ok: true, payload, inputChars: totalChars };
}

async function handleRegister(request, env) {
  if (!validateAdminToken(request, env)) {
    return json({ ok: false, error: "Unauthorized" }, 401);
  }

  const parsed = await readJsonLimited(request, 2048);
  if (!parsed.ok) {
    return json({ ok: false, error: parsed.error }, parsed.status);
  }

  const { key, days } = parsed.data;
  if (!key || !days) {
    return json({ ok: false, error: "Missing key or days" }, 400);
  }
  if (!isValidKeyFormat(key)) {
    return json({ ok: false, error: "Invalid key format" }, 400);
  }

  const parsedDays = parseInt(days, 10);
  if (!Number.isInteger(parsedDays) || parsedDays <= 0 || parsedDays > 3650) {
    return json({ ok: false, error: "Invalid days" }, 400);
  }

  const norm = normalizeKey(key);
  const existing = await env.LICENSE_KV.get(norm);
  if (existing) {
    return json({ ok: false, error: "Key already registered" }, 409);
  }

  const counterRaw = await env.LICENSE_KV.get("__serial__");
  const serial = parseInt(counterRaw || "0", 10) + 1;
  await env.LICENSE_KV.put("__serial__", String(serial));
  await env.LICENSE_KV.put(norm, JSON.stringify({
    days: parsedDays,
    serial,
    activated: false,
    machine_id: null,
    activate_ts: null,
  }));

  return json({ ok: true, serial });
}

async function handleActivate(request, env) {
  if (!validateClientToken(request, env)) {
    return json({ ok: false, error: "Unauthorized" }, 401);
  }

  const parsed = await readJsonLimited(request, 4096);
  if (!parsed.ok) {
    return json({ ok: false, error: parsed.error }, parsed.status);
  }

  const { key, machine_id } = parsed.data;
  if (!key || !machine_id) {
    return json({ ok: false, error: "Missing key or machine_id" }, 400);
  }
  if (!isValidKeyFormat(key)) {
    return json({ ok: false, error: "Key 格式无效" }, 400);
  }

  const norm = normalizeKey(key);
  const record = await loadLicenseRecord(norm, env);
  if (!record) {
    return json({ ok: false, error: "Key 无效或未注册" }, 404);
  }

  if (record.activated && record.machine_id !== machine_id) {
    return json({ ok: false, error: "此 Key 已在其他设备激活，请联系卖家" }, 409);
  }

  const now = Math.floor(Date.now() / 1000);
  const activateTs = record.activated && record.machine_id === machine_id && Number.isInteger(record.activate_ts)
    ? record.activate_ts
    : now;

  record.activated = true;
  record.machine_id = machine_id;
  record.activate_ts = activateTs;
  await env.LICENSE_KV.put(norm, JSON.stringify(record));

  const sessionToken = await createSessionToken(
    {
      v: 1,
      key: norm,
      machine_id,
      activate_ts: activateTs,
    },
    env
  );

  return json({
    ok: true,
    key: displayKey(norm),
    days: record.days,
    activate_ts: activateTs,
    session_token: sessionToken,
  });
}

async function handleVerify(request, env) {
  if (!validateClientToken(request, env)) {
    return json({ ok: false, error: "Unauthorized" }, 401);
  }

  const parsed = await readJsonLimited(request, 4096);
  if (!parsed.ok) {
    return json({ ok: false, error: parsed.error }, parsed.status);
  }

  const { key, machine_id } = parsed.data;
  if (!key || !machine_id) {
    return json({ ok: false, error: "Missing params" }, 400);
  }

  const record = await loadLicenseRecord(key, env);
  if (!record || !record.activated) {
    return json({ ok: false, error: "Key 未激活" }, 404);
  }
  if (record.machine_id !== machine_id) {
    return json({ ok: false, error: "设备不匹配" }, 409);
  }

  const daysLeft = computeDaysLeft(record);
  if (daysLeft <= 0) {
    return json({ ok: false, error: "Key 已过期", days_left: 0 }, 410);
  }

  return json({ ok: true, days_left: daysLeft, activate_ts: record.activate_ts });
}

async function handleRevoke(request, env) {
  if (!validateAdminToken(request, env)) {
    return json({ ok: false, error: "Unauthorized" }, 401);
  }

  const parsed = await readJsonLimited(request, 2048);
  if (!parsed.ok) {
    return json({ ok: false, error: parsed.error }, parsed.status);
  }

  const { key } = parsed.data;
  if (!key) {
    return json({ ok: false, error: "Missing key" }, 400);
  }

  await env.LICENSE_KV.delete(normalizeKey(key));
  return json({ ok: true });
}

async function handleInspect(request, env) {
  if (!validateAdminToken(request, env)) {
    return json({ ok: false, error: "Unauthorized" }, 401);
  }

  const parsed = await readJsonLimited(request, 2048);
  if (!parsed.ok) {
    return json({ ok: false, error: parsed.error }, parsed.status);
  }

  const { key } = parsed.data;
  if (!key) {
    return json({ ok: false, error: "Missing key" }, 400);
  }

  const norm = normalizeKey(key);
  const record = await loadLicenseRecord(norm, env);
  if (!record) {
    return json({ ok: false, error: "Key not found" }, 404);
  }

  const now = Math.floor(Date.now() / 1000);
  const date = todayStamp(now);
  const usage = await loadJsonValue(env, usageCounterKey(norm, date), {
    requests: 0,
    input_chars: 0,
    output_tokens: 0,
    blocked: 0,
    last_seen_ts: 0,
    last_block_reason: "",
  });

  return json({
    ok: true,
    key: displayKey(norm),
    record: {
      serial: record.serial || 0,
      days: record.days || 0,
      activated: Boolean(record.activated),
      machine_id: record.machine_id || null,
      activate_ts: record.activate_ts || null,
      days_left: record.activated ? computeDaysLeft(record) : null,
    },
    usage_today: usage,
    proxy_limits: publicProxyConfig(proxyConfig(env)),
  });
}

async function handleChatCompletions(request, env) {
  const sessionToken = readBearerToken(request);
  const verified = await verifySessionToken(sessionToken, env);
  if (!verified.ok) {
    return json({ error: { message: verified.error, type: "invalid_request_error" } }, 401);
  }

  const { key, machine_id, activate_ts } = verified.payload;
  const record = await loadLicenseRecord(key, env);
  if (!record || !record.activated) {
    return json({ error: { message: "License not active", type: "invalid_request_error" } }, 401);
  }
  if (record.machine_id !== machine_id) {
    return json({ error: { message: "License machine mismatch", type: "invalid_request_error" } }, 403);
  }
  if (record.activate_ts !== activate_ts) {
    return json({ error: { message: "License session is stale, please reactivate", type: "invalid_request_error" } }, 403);
  }

  const daysLeft = computeDaysLeft(record);
  if (daysLeft <= 0) {
    return json({ error: { message: "License expired", type: "invalid_request_error" } }, 403);
  }

  const cfg = proxyConfig(env);
  const parsed = await readJsonLimited(request, cfg.maxBodyBytes);
  if (!parsed.ok) {
    return json({ error: { message: parsed.error, type: "invalid_request_error" } }, parsed.status);
  }

  const validated = validateProxyPayload(parsed.data, cfg);
  if (!validated.ok) {
    return json({ error: { message: validated.error, type: "invalid_request_error" } }, validated.status);
  }

  const quota = await reserveQuota(env, key, machine_id, validated.inputChars, cfg);
  if (!quota.ok) {
    return json(
      { error: { message: quota.error, type: "rate_limit_error" } },
      quota.status,
      { "Retry-After": quota.retryAfter }
    );
  }

  const upstream = await fetch(`${env.AI_BASE_URL || DEFAULT_AI_BASE_URL}/chat/completions`, {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.CLOUD_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(validated.payload),
  });

  const text = await upstream.text();
  await finalizeQuota(env, quota.usageKey, quota.usage, quota.now, text);

  return new Response(text, {
    status: upstream.status,
    headers: {
      "Content-Type": upstream.headers.get("Content-Type") || "application/json",
      ...CORS,
    },
  });
}
