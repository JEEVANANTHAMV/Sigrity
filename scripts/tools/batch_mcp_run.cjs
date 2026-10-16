#!/usr/bin/env node
/**
 * Batch MCP case runner for the Sigrity MCP server.
 *
 * Why this exists: the sibling `mcp-dev-test.cjs` (Forji-Desk's generic MCP debug CLI)
 * spawns a brand-new server process per invocation. Each spawn alone costs several
 * seconds (Prefect/FastMCP banner + import of all tool domains), which is fine for one-off
 * debugging but far too slow for running a whole ordered list of cases (dozens of tool
 * calls, some of which launch real allegro.exe background jobs). This script spawns the
 * server exactly ONCE, talks the same stdio JSON-RPC 2024-11-05 protocol
 * (newline-delimited JSON-RPC 2.0, `initialize` -> `notifications/initialized` ->
 * `tools/call`) over that single long-lived process, and walks an ordered case list from
 * a JSON file, logging every call's real latency and outcome as it goes (NDJSON, flushed
 * per-case) so partial progress survives a crash or manual interruption.
 *
 * Usage:
 *   node batch_mcp_run.cjs <path-to-cases.json>
 *
 * Case shape (see brs_imx8mp_cases.json for a real example):
 *   {
 *     "label": "human-readable case id, must be unique",
 *     "tool": "<mcp tool name>",
 *     "args": { ... },                 // may contain "$savedKey" template placeholders
 *     "saveAs": "savedKey",            // optional: remember this call's session_id/job_id
 *     "isBackgroundJob": true,         // optional: this tool returns a job_id to poll
 *     "waitTimeoutSeconds": 300        // optional, default 300, only used if isBackgroundJob
 *   }
 *
 * Templating: before calling, `args` is walked recursively (through nested objects and
 * arrays) and any string value that is EXACTLY "$<key>" is replaced with whatever was
 * previously saved under that key via an earlier case's `saveAs`. Saved value preference
 * order per call result: structuredContent.session_id, else structuredContent.job_id,
 * else the whole structuredContent object.
 *
 * Background jobs: when isBackgroundJob is true, after the initial tools/call returns,
 * this script automatically calls wait_for_job(job_id, timeout_seconds=waitTimeoutSeconds)
 * then tail_job_log(job_id, max_lines=200) then list_job_files(job_id), and folds all four
 * sub-results into ONE case log entry. The logged latency_ms for such a case is measured
 * from the initial call to wait_for_job returning (tail/list calls are cheap local reads
 * and are excluded from the timed window, though their wall-clock is still absorbed into
 * total_wall_clock_ms for the whole run).
 *
 * Failure handling: ANY error (JSON-RPC error response, thrown exception, tool result with
 * isError:true, or -- for background jobs -- a final job state of "failed") is caught,
 * logged with status "deferred_v2" and the real error text, and the run continues to the
 * next case. Nothing stops the whole run early except an unrecoverable spawn failure.
 */

"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const readline = require("readline");

const MCP_JSON_PATH = path.join(__dirname, "..", "mcp.json");
const SERVER_CWD = path.join(__dirname, "..");
const LOG_DIR = "C:\\Users\\aicoe\\Desktop\\Forji-Desk\\reports\\IMX8MP_BRS_Automation\\devops";
const NDJSON_LOG_PATH = path.join(LOG_DIR, "tool_call_log.ndjson");
const SUMMARY_PATH = path.join(LOG_DIR, "tool_call_summary.json");

const DEFAULT_RPC_TIMEOUT_MS = 30000; // per-JSON-RPC-call timeout (initialize, tools/call envelope itself)
const DEFAULT_WAIT_TIMEOUT_SECONDS = 300;

function normaliseMcpConfig(raw) {
  if (raw && raw.mcpServers && typeof raw.mcpServers === "object") {
    const entries = Object.values(raw.mcpServers);
    if (entries.length > 0) return entries[0];
  }
  return raw;
}

function loadServerConfig() {
  const raw = JSON.parse(fs.readFileSync(MCP_JSON_PATH, "utf-8"));
  const cfg = normaliseMcpConfig(raw);
  if (!cfg || !cfg.command) throw new Error(`Resolved config at ${MCP_JSON_PATH} has no 'command'.`);
  return {
    command: cfg.command,
    args: cfg.args || [],
    cwd: cfg.cwd || SERVER_CWD,
    env: cfg.env || {},
  };
}

/** Same stdio JSON-RPC client contract as mcp-dev-test.cjs's spawnClient, but kept alive
 * across many calls instead of being torn down after one. */
function spawnClient({ command, args, cwd, env }) {
  const cleanEnv = { ...process.env, PYTHONUNBUFFERED: "1", ...env };
  delete cleanEnv.NODE_OPTIONS;
  delete cleanEnv.ELECTRON_RUN_AS_NODE;
  console.error(`[batch-mcp-run] spawning: ${command} ${args.join(" ")}`);
  console.error(`[batch-mcp-run] cwd: ${cwd}`);
  const proc = spawn(command, args, { cwd, stdio: ["pipe", "pipe", "pipe"], windowsHide: true, env: cleanEnv });
  proc.stderr.on("data", (d) => process.stderr.write(`[server stderr] ${d}`));
  proc.on("error", (err) => console.error(`[batch-mcp-run] spawn error: ${err.message}`));
  proc.on("exit", (code, signal) => console.error(`[batch-mcp-run] server exited (code=${code}, signal=${signal})`));
  return proc;
}

let rpcIdCounter = 1;

function rpc(proc, rl, method, params, timeoutMs) {
  const id = rpcIdCounter++;
  return new Promise((resolve, reject) => {
    const onLine = (line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      let data;
      try {
        data = JSON.parse(trimmed);
      } catch {
        return; // non-JSON server log line on stdout; ignore, same as mcp-dev-test.cjs
      }
      if (data.id !== id) return;
      rl.off("line", onLine);
      clearTimeout(timer);
      if (data.error) reject(new Error(typeof data.error === "string" ? data.error : JSON.stringify(data.error)));
      else resolve(data.result);
    };
    const timer = setTimeout(() => {
      rl.off("line", onLine);
      reject(new Error(`timed out after ${timeoutMs}ms waiting for response to ${method}`));
    }, timeoutMs);
    rl.on("line", onLine);
    proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params: params || {} }) + "\n");
  });
}

async function initializeClient(proc, rl) {
  await rpc(proc, rl, "initialize", {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: { name: "batch-mcp-run", version: "1.0.0" },
  }, DEFAULT_RPC_TIMEOUT_MS);
  proc.stdin.write(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized", params: {} }) + "\n");
}

/** Call a tool, timing it. Returns { ms, result, error } -- never throws; errors
 * (JSON-RPC errors, thrown exceptions, or result.isError:true) are captured in `error`. */
async function callTool(proc, rl, toolName, args, timeoutMs) {
  const t0 = Date.now();
  try {
    const result = await rpc(proc, rl, "tools/call", { name: toolName, arguments: args || {} }, timeoutMs);
    const ms = Date.now() - t0;
    if (result && result.isError) {
      const text = extractErrorText(result);
      return { ms, result, error: text || "tool returned isError:true" };
    }
    return { ms, result, error: null };
  } catch (err) {
    return { ms: Date.now() - t0, result: null, error: err.message };
  }
}

function extractErrorText(result) {
  if (!result) return null;
  if (Array.isArray(result.content)) {
    const texts = result.content.filter((c) => c && c.type === "text").map((c) => c.text);
    if (texts.length) return texts.join("\n");
  }
  if (result.structuredContent) return JSON.stringify(result.structuredContent);
  return null;
}

function getStructuredContent(result) {
  return result && result.structuredContent ? result.structuredContent : null;
}

/** Deep-walk args, replacing any string value exactly equal to "$<key>" with the saved value. */
function resolveTemplates(value, saved) {
  if (typeof value === "string") {
    if (value.startsWith("$") && value.length > 1) {
      const key = value.slice(1);
      if (Object.prototype.hasOwnProperty.call(saved, key)) {
        return saved[key];
      }
    }
    return value;
  }
  if (Array.isArray(value)) {
    return value.map((v) => resolveTemplates(v, saved));
  }
  if (value && typeof value === "object") {
    const out = {};
    for (const [k, v] of Object.entries(value)) {
      out[k] = resolveTemplates(v, saved);
    }
    return out;
  }
  return value;
}

function pickSaveValue(structuredContent) {
  if (!structuredContent) return undefined;
  if (structuredContent.session_id !== undefined) return structuredContent.session_id;
  if (structuredContent.job_id !== undefined) return structuredContent.job_id;
  return structuredContent;
}

function appendNdjson(obj) {
  fs.appendFileSync(NDJSON_LOG_PATH, JSON.stringify(obj) + "\n", "utf-8");
}

function shortSummary(obj, maxLen = 300) {
  let s;
  try {
    s = typeof obj === "string" ? obj : JSON.stringify(obj);
  } catch {
    s = String(obj);
  }
  if (!s) return "";
  return s.length > maxLen ? s.slice(0, maxLen) + "...(truncated)" : s;
}

async function runCase(proc, rl, caseDef, index, total, saved) {
  const label = caseDef.label;
  const tool = caseDef.tool;
  const wallT0 = Date.now();
  const resolvedArgs = resolveTemplates(caseDef.args || {}, saved);

  const logEntry = {
    label,
    tool,
    args: resolvedArgs,
    timestamp: new Date().toISOString(),
  };

  const initial = await callTool(proc, rl, tool, resolvedArgs, DEFAULT_RPC_TIMEOUT_MS);

  if (initial.error) {
    logEntry.status = "deferred_v2";
    logEntry.latency_ms = initial.ms;
    logEntry.error = initial.error;
    logEntry.raw_result = initial.result || null;
    finishCase(logEntry, index, total);
    return logEntry;
  }

  const initialStructured = getStructuredContent(initial.result);

  if (caseDef.saveAs) {
    const val = pickSaveValue(initialStructured);
    if (val !== undefined) saved[caseDef.saveAs] = val;
  }

  if (!caseDef.isBackgroundJob) {
    logEntry.status = "succeeded";
    logEntry.latency_ms = initial.ms;
    logEntry.result_summary = shortSummary(initialStructured);
    logEntry.error_or_summary = logEntry.result_summary;
    finishCase(logEntry, index, total);
    return logEntry;
  }

  // Background job lifecycle: wait_for_job -> tail_job_log -> list_job_files, all folded
  // into this same case. latency_ms measures initial call through wait_for_job returning.
  const jobId = (initialStructured && initialStructured.job_id) || null;
  if (!jobId) {
    logEntry.status = "deferred_v2";
    logEntry.latency_ms = initial.ms;
    logEntry.error = "isBackgroundJob=true but no job_id found in structuredContent";
    logEntry.initial_result = initialStructured;
    finishCase(logEntry, index, total);
    return logEntry;
  }

  const waitTimeoutSeconds = caseDef.waitTimeoutSeconds || DEFAULT_WAIT_TIMEOUT_SECONDS;
  const waitTimeoutMs = waitTimeoutSeconds * 1000 + 15000; // RPC envelope timeout padding over the job wait itself
  const waitOutcome = await callTool(proc, rl, "wait_for_job", { job_id: jobId, timeout_seconds: waitTimeoutSeconds }, waitTimeoutMs);
  const latencyMs = Date.now() - wallT0; // initial call -> wait_for_job returning, per spec

  const waitStructured = getStructuredContent(waitOutcome.result);

  const tailOutcome = await callTool(proc, rl, "tail_job_log", { job_id: jobId, max_lines: 200 }, DEFAULT_RPC_TIMEOUT_MS);
  const filesOutcome = await callTool(proc, rl, "list_job_files", { job_id: jobId }, DEFAULT_RPC_TIMEOUT_MS);

  logEntry.job_id = jobId;
  logEntry.latency_ms = latencyMs;
  logEntry.initial_result = initialStructured;
  logEntry.wait_result = waitStructured || waitOutcome.error || null;
  logEntry.tail_log = getStructuredContent(tailOutcome.result) || tailOutcome.error || null;
  logEntry.job_files = getStructuredContent(filesOutcome.result) || filesOutcome.error || null;

  if (waitOutcome.error) {
    logEntry.status = "deferred_v2";
    logEntry.error = waitOutcome.error;
  } else if (waitStructured && waitStructured.error) {
    logEntry.status = "deferred_v2";
    logEntry.error = waitStructured.error;
  } else if (waitStructured && waitStructured.state === "failed") {
    logEntry.status = "deferred_v2";
    logEntry.error = `job ended in state=failed (failure_note: ${waitStructured.failure_note || "none"}, runaway_log_killed: ${waitStructured.runaway_log_killed}, stall_timeout_killed: ${waitStructured.stall_timeout_killed})`;
  } else if (waitStructured && waitStructured.state && waitStructured.state !== "succeeded") {
    // e.g. still "running" after timeout
    logEntry.status = "deferred_v2";
    logEntry.error = `job did not reach state=succeeded within ${waitTimeoutSeconds}s (final state: ${waitStructured.state})`;
  } else {
    logEntry.status = "succeeded";
    logEntry.error_or_summary = shortSummary({
      job_state: waitStructured ? waitStructured.state : "unknown",
      job_dir: waitStructured ? waitStructured.job_dir : undefined,
      file_count: logEntry.job_files && logEntry.job_files.file_count,
    });
  }
  if (!logEntry.error_or_summary) logEntry.error_or_summary = logEntry.error;

  finishCase(logEntry, index, total);
  return logEntry;
}

function finishCase(logEntry, index, total) {
  appendNdjson(logEntry);
  console.log(`[${index}/${total}] ${logEntry.label} -> ${logEntry.status} (${logEntry.latency_ms} ms)`);
}

async function main() {
  const casesPath = process.argv[2];
  if (!casesPath) {
    console.error("Usage: node batch_mcp_run.cjs <path-to-cases.json>");
    process.exit(1);
  }

  fs.mkdirSync(LOG_DIR, { recursive: true });

  // Resume support: if the NDJSON log already has entries (e.g. a prior interrupted run),
  // skip labels already completed instead of re-running them.
  const alreadyDone = new Set();
  if (fs.existsSync(NDJSON_LOG_PATH)) {
    const existing = fs.readFileSync(NDJSON_LOG_PATH, "utf-8").split("\n").filter(Boolean);
    for (const line of existing) {
      try {
        const obj = JSON.parse(line);
        if (obj.label) alreadyDone.add(obj.label);
      } catch {
        // ignore malformed lines
      }
    }
    if (alreadyDone.size > 0) {
      console.error(`[batch-mcp-run] resuming: ${alreadyDone.size} case(s) already in ${NDJSON_LOG_PATH}, will skip them.`);
    }
  }

  const cases = JSON.parse(fs.readFileSync(casesPath, "utf-8"));
  const total = cases.length;
  const saved = {};
  const allResults = [];

  // Re-hydrate `saved` from prior NDJSON entries so templated args referencing an
  // earlier-saved session_id/job_id still resolve correctly after a resume.
  if (fs.existsSync(NDJSON_LOG_PATH)) {
    const existing = fs.readFileSync(NDJSON_LOG_PATH, "utf-8").split("\n").filter(Boolean);
    const caseByLabel = new Map(cases.map((c) => [c.label, c]));
    for (const line of existing) {
      try {
        const obj = JSON.parse(line);
        const def = caseByLabel.get(obj.label);
        if (def && def.saveAs && obj.initial_result) {
          const val = pickSaveValue(obj.initial_result);
          if (val !== undefined) saved[def.saveAs] = val;
        } else if (def && def.saveAs && obj.result_summary) {
          // non-background saved case: result_summary is a JSON string of structuredContent
          try {
            const parsed = JSON.parse(obj.result_summary);
            const val = pickSaveValue(parsed);
            if (val !== undefined) saved[def.saveAs] = val;
          } catch {
            /* ignore */
          }
        }
      } catch {
        /* ignore malformed line */
      }
    }
  }

  const cfg = loadServerConfig();
  const proc = spawnClient(cfg);
  const rl = readline.createInterface({ input: proc.stdout });

  const wallClockStart = Date.now();
  let fatalError = null;

  try {
    await initializeClient(proc, rl);

    let idx = 0;
    for (const caseDef of cases) {
      idx++;
      if (alreadyDone.has(caseDef.label)) {
        console.log(`[${idx}/${total}] ${caseDef.label} -> skipped (already in log)`);
        continue;
      }
      try {
        const entry = await runCase(proc, rl, caseDef, idx, total, saved);
        allResults.push(entry);
      } catch (err) {
        // Should not normally happen (runCase catches internally), but guard anyway so
        // one case can never kill the whole run.
        const entry = {
          label: caseDef.label,
          tool: caseDef.tool,
          status: "deferred_v2",
          latency_ms: 0,
          error: `unexpected runner exception: ${err.message}`,
        };
        appendNdjson(entry);
        console.log(`[${idx}/${total}] ${caseDef.label} -> deferred_v2 (0 ms) [runner exception]`);
        allResults.push(entry);
      }
    }
  } catch (err) {
    fatalError = err;
    console.error(`[batch-mcp-run] FATAL: ${err.message}`);
  } finally {
    proc.kill();
  }

  // Build summary from the FULL ndjson log (covers both this run and any earlier resumed
  // partial run) so tool_call_summary.json always reflects the complete case list.
  const allLines = fs.existsSync(NDJSON_LOG_PATH)
    ? fs.readFileSync(NDJSON_LOG_PATH, "utf-8").split("\n").filter(Boolean).map((l) => JSON.parse(l))
    : [];
  const byLabel = new Map();
  for (const entry of allLines) byLabel.set(entry.label, entry); // last write wins

  const summaryCases = [];
  let succeeded = 0;
  let deferred = 0;
  let failed = 0;
  for (const caseDef of cases) {
    const entry = byLabel.get(caseDef.label);
    if (!entry) {
      summaryCases.push({ label: caseDef.label, tool: caseDef.tool, status: "not_run", latency_ms: 0, error_or_summary: "never reached (earlier fatal error)" });
      failed++;
      continue;
    }
    summaryCases.push({
      label: entry.label,
      tool: entry.tool,
      status: entry.status,
      latency_ms: entry.latency_ms || 0,
      error_or_summary: entry.error_or_summary || entry.error || entry.result_summary || "",
    });
    if (entry.status === "succeeded") succeeded++;
    else if (entry.status === "deferred_v2") deferred++;
    else failed++;
  }

  const summary = {
    total_cases: cases.length,
    succeeded,
    deferred,
    failed,
    total_wall_clock_ms: Date.now() - wallClockStart,
    cases: summaryCases,
  };
  fs.writeFileSync(SUMMARY_PATH, JSON.stringify(summary, null, 2), "utf-8");
  console.log(`\nSummary written to ${SUMMARY_PATH}`);
  console.log(`total=${summary.total_cases} succeeded=${succeeded} deferred=${deferred} failed=${failed} wall_clock_ms=${summary.total_wall_clock_ms}`);

  if (fatalError) process.exitCode = 1;
}

main().catch((err) => {
  console.error(`[batch-mcp-run] UNHANDLED: ${err.stack || err.message}`);
  process.exit(1);
});
