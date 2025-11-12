'use strict';

const { spawn } = require('child_process');
const { URL } = require('url');
const http = require('http');
const https = require('https');
const { pathToFileURL } = require('url');
const fs = require('fs').promises;
const path = require('path');

// --- helpers: normalize booleans/numbers from TOOL_REQUEST strings ---
function isTrue(v) {
  if (typeof v === 'boolean') return v;
  if (v === null || v === undefined) return false;
  const s = String(v).trim().toLowerCase();
  return s === 'true' || s === '1' || s === 'yes' || s === 'on' || s === 'y';
}
function toInt(v, def = null) {
  const n = parseInt(v, 10);
  return Number.isFinite(n) ? n : def;
}

/**
 * Read entire stdin as a single UTF-8 string
 * @returns {Promise<string>}
 */
function readAllStdin() {
  return new Promise((resolve, reject) => {
    let data = '';
    try {
      process.stdin.setEncoding('utf8');
      process.stdin.on('data', chunk => { data += chunk; });
      process.stdin.on('end', () => resolve(data));
      process.stdin.on('error', reject);
    } catch (e) {
      reject(e);
    }
  });
}

/**
 * Emit one-time success JSON WITHOUT exiting (async plugin keeps running)
 * The server will read this and return to AI while we continue background work
 */
function emitImmediateSuccess(result) {
  try {
    console.log(JSON.stringify({ status: 'success', result }));
  } catch (e) {
    // If serialization fails, still try to return something
    console.log(JSON.stringify({ status: 'success', result: String(result) }));
  }
  // Important: do NOT exit; background work continues
}

/**
 * Emit error and exit immediately (for non-submit, or fatal bootstrap errors)
 */
function emitImmediateError(code, message, extra = {}) {
  try {
    console.log(JSON.stringify({ status: 'error', code, error: message, ...extra }));
  } catch {
    console.log(JSON.stringify({ status: 'error', code, error: message }));
  }
  process.exit(1);
}

/**
 * POST JSON to callback URL
 * @param {string} url
 * @param {any} body
 * @param {number} timeoutMs
 * @returns {Promise<{statusCode:number, body:string}>}
 */
function httpPostJson(url, body, timeoutMs = 30000) {
  return new Promise((resolve, reject) => {
    let parsed;
    try {
      parsed = new URL(url);
    } catch (e) {
      return reject(Object.assign(new Error(`Invalid callback URL: ${url}`), { code: 'BAD_URL' }));
    }
    const lib = parsed.protocol === 'https:' ? https : http;

    const payload = Buffer.from(JSON.stringify(body), 'utf8');
    const req = lib.request({
      protocol: parsed.protocol,
      hostname: parsed.hostname,
      port: parsed.port || (parsed.protocol === 'https:' ? 443 : 80),
      path: parsed.pathname + (parsed.search || ''),
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Content-Length': String(payload.length)
      },
      timeout: timeoutMs
    }, (res) => {
      let resData = '';
      res.setEncoding('utf8');
      res.on('data', chunk => { resData += chunk; });
      res.on('end', () => resolve({ statusCode: res.statusCode || 0, body: resData }));
    });

    req.on('error', (err) => reject(Object.assign(err, { code: 'HTTP_POST_ERROR' })));
    req.on('timeout', () => {
      try { req.destroy(new Error('HTTP POST timeout')); } catch {}
      reject(Object.assign(new Error('HTTP POST timeout'), { code: 'HTTP_TIMEOUT' }));
    });

    req.write(payload);
    req.end();
  });
}

// --- Callback reliability helpers ---
function sleep(ms) {
  return new Promise(r => setTimeout(r, ms));
}

function isRetryableStatus(code) {
  if (!code) return true;
  // Retry on 5xx, 408, 429
  if (code >= 500) return true;
  if (code === 408 || code === 429) return true;
  return false;
}

/**
 * Retry wrapper with exponential backoff and jitter
 * @param {string} url
 * @param {any} body
 * @param {object} opts
 * @param {number} opts.attempts - max attempts
 * @param {number} opts.baseDelayMs - initial delay
 * @param {number} opts.maxDelayMs - cap delay
 * @param {number} opts.timeoutPerAttemptMs - per attempt timeout
 */
async function httpPostJsonWithRetry(url, body, opts = {}) {
  const attempts = Math.max(1, opts.attempts || 8);
  const baseDelay = Math.max(100, opts.baseDelayMs || 1000);
  const maxDelay = Math.max(baseDelay, opts.maxDelayMs || 15000);
  const perAttemptTimeout = Math.max(1000, opts.timeoutPerAttemptMs || 30000);

  let lastErr = null;
  for (let i = 1; i <= attempts; i++) {
    try {
      const { statusCode, body: resBody } = await httpPostJson(url, body, perAttemptTimeout);
      if (statusCode >= 200 && statusCode < 300) {
        return { statusCode, body: resBody };
      }
      if (!isRetryableStatus(statusCode)) {
        // Do not retry on non-retryable client errors
        const e = new Error(`Non-retryable HTTP ${statusCode}`);
        e.statusCode = statusCode;
        e.body = resBody;
        throw e;
      }
      lastErr = new Error(`Retryable HTTP ${statusCode}`);
      lastErr.statusCode = statusCode;
      lastErr.body = resBody;
    } catch (e) {
      lastErr = e;
    }
    // backoff with jitter
    const delay = Math.min(maxDelay, baseDelay * Math.pow(2, i - 1));
    const jitter = Math.floor(Math.random() * Math.floor(delay * 0.2));
    const wait = delay + jitter;
    process.stderr.write(`[YtDLPDownload] Callback attempt ${i}/${attempts} failed: ${lastErr?.message || 'unknown'}. Retrying in ${wait}ms\n`);
    await sleep(wait);
  }
  throw lastErr || new Error('Callback failed without error detail');
}

/**
 * Spawn yt-dlp with safe args array
 * @param {string} ytdlpPath
 * @param {string[]} args
 * @param {number} timeoutMs
 * @returns {Promise<{ code:number, stdout:string, stderr:string }>}
 */
function runYtDlp(ytdlpPath, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = spawn(ytdlpPath, args, {
      shell: false,
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe']
    });

    let stdout = '';
    let stderr = '';
    let finished = false;

    const timer = timeoutMs > 0 ? setTimeout(() => {
      if (finished) return;
      finished = true;
      try { child.kill('SIGKILL'); } catch {}
      reject(Object.assign(new Error(`yt-dlp timeout after ${timeoutMs}ms`), {
        code: 'TIMEOUT', stdout, stderr
      }));
    }, timeoutMs) : null;

    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');
    child.stdout.on('data', d => { stdout += d; });
    child.stderr.on('data', d => { stderr += d; });

    child.on('error', (err) => {
      if (timer) clearTimeout(timer);
      if (finished) return;
      finished = true;
      reject(Object.assign(err, { code: 'SPAWN_ERROR', stdout, stderr }));
    });

    child.on('close', (code) => {
      if (timer) clearTimeout(timer);
      if (finished) return;
      finished = true;
      resolve({ code, stdout, stderr });
    });
  });
}

/**
 * Build common flags (cookies/proxy/ffmpeg)
 */
function buildCommonFlags(env, req) {
  const flags = ['--no-colors', '--no-progress'];
  if (env.ffmpegPath) {
    flags.push('--ffmpeg-location', env.ffmpegPath);
  }
  const cookies =
    req.cookiesFromBrowser ??
    req.cookies_from_browser ??
    req.cookies ??
    env.cookiesFromBrowser;
  if (cookies && String(cookies).trim().toLowerCase() !== 'none') {
    flags.push('--cookies-from-browser', String(cookies));
  }
  const proxy = req.proxy ?? env.proxy;
  if (proxy) {
    flags.push('--proxy', String(proxy));
  }
  if (isTrue(req.noCacheDir)) {
    flags.push('--no-cache-dir');
  }
  // Default base paths
  const homePath = req.pathsHome || env.downloadDir;
  if (homePath) {
    flags.push('-P', `home:${homePath}`);
  }
  if (req.pathsTemp) {
    flags.push('-P', `temp:${req.pathsTemp}`);
  }
  if (req.pathsSubtitle) {
    flags.push('-P', `subtitle:${req.pathsSubtitle}`);
  }
  return flags;
}

/**
 * Build download flags for a single item
 * @param {*} env
 * @param {*} req
 * @param {string} url
 * @returns {string[]}
 */
function buildDownloadArgs(env, req, url) {
  const args = buildCommonFlags(env, req);

  // Output template
  const outputTemplate = req.outputTemplate || '%(title)s [%(id)s].%(ext)s';
  args.push('-o', String(outputTemplate));

  // Format selection
  if (req.format) {
    args.push('-f', String(req.format));
  } else if (isTrue(req.audioOnly)) {
    // 當僅需音訊且未顯式指定 format，優先選擇音訊流，避免完整影片下載後再轉檔
    // 仍會配合 -x 與 --audio-format 進行最終轉檔（如 mp3）
    args.push('-f', 'bestaudio/best');
  }
  if (req.formatSort) {
    args.push('--format-sort', String(req.formatSort));
  }

  // Subtitles
  if (req.subLangs) {
    args.push('--sub-langs', String(req.subLangs));
  }
  if (isTrue(req.writeSubs)) {
    args.push('--write-subs');
  }
  if (isTrue(req.writeAutoSubs)) {
    args.push('--write-auto-subs');
  }
  if (isTrue(req.embedSubs)) {
    args.push('--embed-subs');
  }

  // Subtitle format (srt/ass/vtt)
  if (req.subFormat) {
    args.push('--sub-format', String(req.subFormat));
  } else if (isTrue(req.writeSubs) || isTrue(req.writeAutoSubs)) {
    // 預設輸出易用的文字字幕
    args.push('--sub-format', 'srt');
  }

  // Allow subtitles-only extraction without downloading media
  if (isTrue(req.skipDownload)) {
    args.push('--skip-download');
  }

  // Anti-429 / rate limiting knobs (可由請求覆寫)
  if (req.sleepRequests) {
    args.push('--sleep-requests', String(req.sleepRequests));
  } else if (isTrue(req.writeSubs) || isTrue(req.writeAutoSubs)) {
    // 若請求字幕，預設稍作延遲以降低 429 機率
    args.push('--sleep-requests', '0.5');
  }
  if (req.retrySleep) {
    // e.g. "linear=1::2" or "exp=1:20"
    args.push('--retry-sleep', String(req.retrySleep));
  }
  if (req.extractorRetries) {
    args.push('--extractor-retries', String(req.extractorRetries));
  } else if (isTrue(req.writeSubs) || isTrue(req.writeAutoSubs)) {
    args.push('--extractor-retries', '3');
  }
  if (req.sleepSubtitles) {
    args.push('--sleep-subtitles', String(req.sleepSubtitles));
  }
  if (req.extractorArgs) {
    // e.g. "youtube:player_client=web_safari"
    args.push('--extractor-args', String(req.extractorArgs));
  } else if ((isTrue(req.writeSubs) || isTrue(req.writeAutoSubs)) && /youtube\.com|youtu\.be/.test(String(url))) {
    // 字幕場景缺省給 Youtube 一個較穩定的 player client，降低 429 機率
    args.push('--extractor-args', 'youtube:player_client=web_safari');
  }
  if (req.limitRate) {
    args.push('--limit-rate', String(req.limitRate));
  }
  if (isTrue(req.noOverwrites)) {
    args.push('-w');
  }
  if (isTrue(req.forceOverwrites)) {
    args.push('--force-overwrites');
  }

  // Subtitle format (srt/ass/vtt...)
  if (req.subFormat) {
    args.push('--sub-format', String(req.subFormat));
  }

  // Allow subtitles-only extraction without downloading media
  if (isTrue(req.skipDownload)) {
    args.push('--skip-download');
  }

  // Anti-429/rate-limiting knobs
  if (req.sleepRequests) {
    args.push('--sleep-requests', String(req.sleepRequests));
  }
  if (req.retrySleep) {
    // e.g. "linear=1::2" or "exp=1:20"
    args.push('--retry-sleep', String(req.retrySleep));
  }
  if (req.extractorRetries) {
    args.push('--extractor-retries', String(req.extractorRetries));
  }
  if (req.sleepSubtitles) {
    args.push('--sleep-subtitles', String(req.sleepSubtitles));
  }
  if (req.extractorArgs) {
    // e.g. "youtube:player_client=web_safari"
    args.push('--extractor-args', String(req.extractorArgs));
  } else if ((isTrue(req.writeSubs) || isTrue(req.writeAutoSubs)) && /(?:youtube\.com|youtu\.be)/i.test(String(url))) {
    // 若請求字幕且為 YouTube，預設使用較穩定的 player client，降低 429 機率
    args.push('--extractor-args', 'youtube:player_client=web_safari');
  }
  if (req.limitRate) {
    args.push('--limit-rate', String(req.limitRate));
  }
  if (isTrue(req.noOverwrites)) {
    args.push('-w');
  }
  if (isTrue(req.forceOverwrites)) {
    args.push('--force-overwrites');
  }

  // Subtitle format (e.g., srt/ass/vtt)
  if (req.subFormat) {
    args.push('--sub-format', String(req.subFormat));
  }

  // Allow subtitles-only retry without redownloading media
  if (isTrue(req.skipDownload)) {
    args.push('--skip-download');
  }

  // Anti-429 tuning (optional)
  if (req.sleepRequests) {
    args.push('--sleep-requests', String(req.sleepRequests));
  }
  if (req.retrySleep) {
    // e.g. "linear=1::2" or "exp=1:20"
    args.push('--retry-sleep', String(req.retrySleep));
  }
  if (req.extractorRetries) {
    args.push('--extractor-retries', String(req.extractorRetries));
  }

  // Audio extraction
  if (isTrue(req.audioOnly)) {
    args.push('-x');
    if (req.audioFormat) {
      args.push('--audio-format', String(req.audioFormat));
    }
    if (req.audioQuality) {
      args.push('--audio-quality', String(req.audioQuality));
    }
  }

  // Merge/recode/remux
  if (req.mergeOutputFormat) {
    args.push('--merge-output-format', String(req.mergeOutputFormat));
  }
  if (req.recodeVideo) {
    args.push('--recode-video', String(req.recodeVideo));
  }
  if (req.remuxVideo) {
    args.push('--remux-video', String(req.remuxVideo));
  }

  // Performance / network
  if (req.concurrentFragments !== undefined && req.concurrentFragments !== null) {
    const cf = toInt(req.concurrentFragments);
    if (cf) args.push('-N', String(cf));
  }
  if (req.throttledRate) {
    args.push('--throttled-rate', String(req.throttledRate));
  }
  if (req.playlistItems) {
    args.push('-I', String(req.playlistItems));
  }
  if (req.downloadSections) {
    // Can be specified multiple times; allow CSV or array
    const sections = Array.isArray(req.downloadSections)
      ? req.downloadSections
      : String(req.downloadSections).split(',').map(s => s.trim()).filter(Boolean);
    for (const s of sections) {
      args.push('--download-sections', s);
    }
  }
  if (req.impersonate) {
    args.push('--impersonate', String(req.impersonate));
  }

  // Print final moved file path(s) after post-processing
  args.push('--print', 'after_move:filepath');

  // Finally, the URL
  args.push(String(url));

  return args;
}

/**
 * Detect ascending numeric suffixes for batch mode: command1/url1/...
 */
function detectBatchIndices(request) {
  const indices = new Set();
  for (const key of Object.keys(request)) {
    const m = key.match(/^([A-Za-z_]+?)(\d+)$/);
    if (m) indices.add(Number(m[2]));
  }
  return Array.from(indices).sort((a, b) => a - b);
}

/**
 * Build sub-request object for a given index
 */
function buildSubRequest(request, index) {
  const sub = {};
  for (const [k, v] of Object.entries(request)) {
    const m = k.match(/^(.+?)(\d+)$/);
    if (m && Number(m[2]) === index) {
      sub[m[1]] = v;
    }
  }
  return sub;
}

/**
 * Generate a request id
 */
function generateRequestId() {
  const now = new Date();
  const stamp = now.toISOString().replace(/[:.]/g, '-');
  const rnd = Math.random().toString(36).slice(2, 8);
  return `${stamp}-${rnd}`;
}

/**
 * Normalize a file path to file:// URL
 */
function toFileUrl(p) {
  try {
    return pathToFileURL(p).href;
  } catch {
    return null;
  }
}

/**
 * Run one download job (single URL)
 * @param {*} env
 * @param {*} req
 * @param {string} url
 */
async function runOne(env, req, url) {
  const args = buildDownloadArgs(env, req, url);
  const startedAt = Date.now();
  const { code, stdout, stderr } = await runYtDlp(env.ytdlpPath, args, env.timeoutMs);

  // Parse printed file paths (each line is a final file path)
  const files = stdout.split(/\r?\n/).map(s => s.trim()).filter(Boolean).map(p => ({
    path: p,
    fileUrl: toFileUrl(p)
  }));

  // 字幕診斷：若請求字幕但提取受限或不可用，標註狀態
  let subsStatus = 'none';
  const subRequested = isTrue(req.writeSubs) || isTrue(req.writeAutoSubs);
  if (subRequested) {
    subsStatus = 'ok';
    if (/HTTP\s*Error\s*429|Too\s*Many\s*Requests|rate.?limit|quota|exceeded/i.test(stderr)) {
      subsStatus = 'rate_limited';
    } else if (/no subtitles|subtitles.*not available|unable to download subtitle|無字幕|无字幕/i.test(stderr)) {
      subsStatus = 'not_available';
    } else if (/subtitle.*(error|failed)/i.test(stderr)) {
      subsStatus = 'failed';
    }
  }

  // 提示：若請求 audioOnly 但最終副檔名非期望音訊格式，加入診斷資訊以利排查
  let postprocessNote;
  if (isTrue(req.audioOnly)) {
    const desired = req.audioFormat ? String(req.audioFormat).toLowerCase() : null;
    const firstPath = files[0]?.path;
    const ext = firstPath ? (path.extname(firstPath).slice(1) || '').toLowerCase() : null;
    if (desired && ext && ext !== desired) {
      if (/ffmpeg/i.test(stderr) && /(not found|not recognized|无法找到|未找到)/i.test(stderr)) {
        postprocessNote = 'ffmpeg/ffprobe 未可用；音訊抽取失敗，保留原容器';
      } else if (/post[- ]processing failed|conversion failed|后处理失败|轉檔失敗/i.test(stderr)) {
        postprocessNote = '後處理轉檔失敗，詳見 stderr';
      }
    }
  }

  return {
    url,
    exitCode: code,
    success: code === 0,
    files,
    durationMs: Date.now() - startedAt,
    // Keep short snippets to avoid huge payloads
    stdout: stdout.length > 4000 ? stdout.slice(-4000) : stdout,
    stderr: stderr.length > 4000 ? stderr.slice(-4000) : stderr,
    postprocessNote,
    subsStatus
  };
}

/**
 * Orchestrate submit: single or batch with commandX/urlX
 */
async function orchestrateSubmit(env, request, requestId) {
  const startedAt = Date.now();

  const indices = detectBatchIndices(request);
  const items = [];

  if (indices.length > 0) {
    // Batch mode
    for (const idx of indices) {
      const sub = buildSubRequest(request, idx);
      const subCmd = (sub.command ?? sub.cmd ?? '').toString();
      if (subCmd !== 'submit') {
        items.push({ index: idx, success: false, error: `Unsupported command in batch: ${subCmd}` });
        continue;
      }
      const url = sub.url ?? sub.URL ?? sub.link;
      if (!url) {
        items.push({ index: idx, success: false, error: 'Missing urlX' });
        continue;
      }
      try {
        const one = await runOne(env, { ...request, ...sub }, String(url));
        items.push({ index: idx, ...one });
      } catch (e) {
        items.push({
          index: idx,
          url: String(url),
          success: false,
          exitCode: -1,
          error: e.message,
          code: e.code ?? 'ERROR',
          stderr: e.stderr ? String(e.stderr).slice(-4000) : undefined
        });
      }
    }
  } else {
    // Single
    const url = request.url ?? request.URL ?? request.link;
    if (!url) {
      return {
        requestId,
        status: 'Failed',
        error: 'Missing required parameter: url',
        items: [],
        startedAt,
        finishedAt: Date.now()
      };
    }
    try {
      const one = await runOne(env, request, String(url));
      items.push(one);
    } catch (e) {
      items.push({
        url: String(url),
        success: false,
        exitCode: -1,
        error: e.message,
        code: e.code ?? 'ERROR',
        stderr: e.stderr ? String(e.stderr).slice(-4000) : undefined
      });
    }
  }

  const succeedCount = items.filter(x => x.success).length;
  const failedCount = items.length - succeedCount;

  // Compose a human text summary
  const summaryLines = [];
  summaryLines.push(`YtDLPDownload 任務完成：總數 ${items.length}，成功 ${succeedCount}，失敗 ${failedCount}`);
  for (const it of items) {
    const tag = typeof it.index === 'number' ? `#${it.index} ` : '';
    const marker = it.success ? '✅' : '❌';
    const firstFile = it.files && it.files[0] ? it.files[0].path : '';
    summaryLines.push(`${marker} ${tag}${it.url || ''}${firstFile ? ' → ' + firstFile : ''}`);
  }
  const summaryText = summaryLines.join('\n');

  // 若有字幕請求但存在字幕失敗/受限，整體狀態標記為 Partial
  const hasSubsIssue = items.some(it => it.subsStatus && it.subsStatus !== 'ok' && it.subsStatus !== 'none');

  // Build callback payload compatible with VCP async result expectations
  const finalStatus =
    failedCount === 0
      ? (hasSubsIssue ? 'Partial' : 'Succeed')
      : (succeedCount > 0 ? 'Partial' : 'Failed');

  const payload = {
    requestId,
    status: finalStatus,
    startedAt,
    finishedAt: Date.now(),
    items,
    content: [
      { type: 'text', text: summaryText }
    ]
  };

  return payload;
}

async function main() {
  // Bootstrap request
  let reqText = '';
  try {
    reqText = (await readAllStdin()).trim();
    if (!reqText) {
      emitImmediateError('NO_INPUT', 'Empty stdin');
      return;
    }
  } catch (e) {
    emitImmediateError('READ_ERROR', e.message);
    return;
  }

  let request;
  try {
    request = JSON.parse(reqText);
  } catch (e) {
    emitImmediateError('BAD_JSON', `Invalid JSON from stdin: ${e.message}`);
    return;
  }

  // Load environment defaults
  const defaultCbBase =
    process.env.CALLBACK_BASE_URL
    || (process.env.SERVER_PORT ? `http://127.0.0.1:${process.env.SERVER_PORT}/plugin-callback`
                                : 'http://localhost:6005/plugin-callback');

  const env = {
    ytdlpPath: process.env.YTDLP_PATH || 'yt-dlp',
    ffmpegPath: process.env.FFMPEG_PATH || '',
    downloadDir: process.env.DOWNLOAD_DIR || './file/video',
    cookiesFromBrowser: process.env.COOKIES_FROM_BROWSER || 'edge',
    proxy: process.env.PROXY || '',
    timeoutMs: Number.parseInt(process.env.TIMEOUT_MS || '3600000', 10),
    callbackBaseUrl: defaultCbBase,
    pluginNameForCallback: process.env.PLUGIN_NAME_FOR_CALLBACK || 'YtDLPDownload',
    projectBasePath: process.env.PROJECT_BASE_PATH || '',
    callbackMaxAttempts: Number.parseInt(process.env.CALLBACK_MAX_ATTEMPTS || '8', 10),
    callbackBaseDelayMs: Number.parseInt(process.env.CALLBACK_BASE_DELAY_MS || '1000', 10),
    callbackMaxDelayMs: Number.parseInt(process.env.CALLBACK_MAX_DELAY_MS || '15000', 10)
  };

  const command = (request.command ?? request.cmd ?? '').toString();

  if (command === 'submit' || Object.keys(request).some(k => /^command\d+$/.test(k))) {
    // Prepare a request id
    const requestId = request.requestId || generateRequestId();

    // Emit placeholder immediately
    const placeholder = `下載任務 (ID: ${requestId}) 已提交。\n這是一個動態占位符，完成後系統會自動替換為最終結果。\n請在你的回覆中包含以下占位符原文：{{VCP_ASYNC_RESULT::YtDLPDownload::${requestId}}}`;
    emitImmediateSuccess(placeholder);

    // Detach background flow
    (async () => {
      try {
        const resultPayload = await orchestrateSubmit(env, request, requestId);
        const cbUrl = `${env.callbackBaseUrl.replace(/\/$/, '')}/${encodeURIComponent(env.pluginNameForCallback)}/${encodeURIComponent(requestId)}`;

        // Attempt robust callback with retries
        try {
          const { statusCode, body } = await httpPostJsonWithRetry(cbUrl, resultPayload, {
            attempts: env.callbackMaxAttempts,
            baseDelayMs: env.callbackBaseDelayMs,
            maxDelayMs: env.callbackMaxDelayMs,
            timeoutPerAttemptMs: 30000
          });
          process.stderr.write(`[YtDLPDownload] Callback ${statusCode} ${cbUrl}\n`);
          if (statusCode < 200 || statusCode >= 300) {
            process.stderr.write(`[YtDLPDownload] Callback response: ${body?.slice?.(0, 400)}\n`);
          }
        } catch (cbErr) {
          process.stderr.write(`[YtDLPDownload] Callback permanently failed: ${cbErr.message}\n`);
          // Fallback: write to VCPAsyncResults so placeholder替换仍可命中
          if (env.projectBasePath) {
            try {
              const resultsDir = path.join(env.projectBasePath, 'VCPAsyncResults');
              await fs.mkdir(resultsDir, { recursive: true });
              const resultFilePath = path.join(resultsDir, `${env.pluginNameForCallback}-${requestId}.json`);
              await fs.writeFile(resultFilePath, JSON.stringify(resultPayload, null, 2), 'utf8');
              process.stderr.write(`[YtDLPDownload] Fallback wrote async result to ${resultFilePath}\n`);
            } catch (fsErr) {
              process.stderr.write(`[YtDLPDownload] Fallback write failed: ${fsErr.message}\n`);
            }
          } else {
            process.stderr.write('[YtDLPDownload] PROJECT_BASE_PATH not set; cannot write fallback result file.\n');
          }
        }
      } catch (e) {
        process.stderr.write(`[YtDLPDownload] Background error: ${e.message}\n`);
      } finally {
        // Exit after background completes
        process.exit(0);
      }
    })();

    // Keep process alive until background finishes (nothing else to do here)
    return;
  }

  if (command === 'query') {
    // Optional: not maintaining local state; advise to check server-side result files
    emitImmediateSuccess('此外掛不維護本地狀態，請直接透過 VCP 主機的 async 結果檔或前端查詢先前的 requestId。');
    process.exit(0);
    return;
  }

  emitImmediateError('UNKNOWN_COMMAND', `Unknown command: ${command}`);
}

main().catch(e => {
  emitImmediateError(e.code ?? 'FATAL', e.message ?? String(e));
});