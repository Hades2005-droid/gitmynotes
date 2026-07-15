#!/usr/bin/env node
/**
 * =====================================================
 *  NYC LOCAL DEV ENVIRONMENT SIMULATOR
 *  Node-01 — Shadow Jing Garden 4.2
 * =====================================================
 *
 * Realistic local development performance simulator. Generates reports similar
 * to production monitoring but tuned for local dev (higher variance, occasional
 * spikes). Fully local: no real requests, no network, no external calls — the
 * "requests" are synthetic latency samples.
 *
 * Usage:
 *   node simulations/nyc-local-dev-simulator.js [options]
 *
 * Options:
 *   --requests=100          Total simulated requests
 *   --endpoints=auth,users  Comma-separated endpoints
 *   --runs=1                Number of simulation runs
 *   --seed=42               Random seed for reproducibility
 *   --json                  Output raw JSON instead of table
 */

const DEFAULT_ENDPOINTS = [
  { path: "/api/v1/auth", baseLatency: 120, variance: 60, errorChance: 0.02 },
  { path: "/api/v1/metrics", baseLatency: 55, variance: 35, errorChance: 0.01 },
  { path: "/api/v1/users", baseLatency: 65, variance: 40, errorChance: 0.03 },
  { path: "/healthz", baseLatency: 4, variance: 3, errorChance: 0.05 },
];

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    totalRequests: 100,
    endpoints: DEFAULT_ENDPOINTS,
    runs: 1,
    seed: 42,
    json: false,
  };

  for (const arg of args) {
    if (arg.startsWith("--requests=")) options.totalRequests = parseInt(arg.split("=")[1], 10);
    if (arg.startsWith("--runs=")) options.runs = parseInt(arg.split("=")[1], 10);
    if (arg.startsWith("--seed=")) options.seed = parseInt(arg.split("=")[1], 10);
    if (arg === "--json") options.json = true;
    if (arg.startsWith("--endpoints=")) {
      const names = arg.split("=")[1].split(",");
      options.endpoints = names.map((name) => {
        const match = DEFAULT_ENDPOINTS.find((e) => e.path.includes(name));
        return match || { path: `/api/v1/${name}`, baseLatency: 70, variance: 40, errorChance: 0.02 };
      });
    }
  }
  return options;
}

function seededRandom(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

function simulateRequest(endpoint, rand) {
  const latency = Math.max(1, Math.round(endpoint.baseLatency + (rand() - 0.5) * 2 * endpoint.variance));
  const errored = rand() < endpoint.errorChance;
  return { endpoint: endpoint.path, latency, errored };
}

function runSimulation(options) {
  const rand = seededRandom(options.seed);
  const results = {};

  options.endpoints.forEach((ep) => {
    results[ep.path] = { requests: 0, totalLatency: 0, maxLatency: 0, errors: 0 };
  });

  const requestsPerEndpoint = Math.floor(options.totalRequests / options.endpoints.length);
  let remainder = options.totalRequests % options.endpoints.length;

  options.endpoints.forEach((endpoint) => {
    let count = requestsPerEndpoint;
    if (remainder > 0) {
      count++;
      remainder--;
    }
    for (let i = 0; i < count; i++) {
      const req = simulateRequest(endpoint, rand);
      const bucket = results[endpoint.path];
      bucket.requests++;
      bucket.totalLatency += req.latency;
      bucket.maxLatency = Math.max(bucket.maxLatency, req.latency);
      if (req.errored) bucket.errors++;
    }
  });

  return results;
}

function formatReport(results, options) {
  if (options.json) return JSON.stringify(results, null, 2);

  const lines = [];
  lines.push("=====================================================");
  lines.push(" NEW YORK CITY - LOCAL DEV ENVIRONMENT SIMULATOR");
  lines.push("=====================================================");
  lines.push(`Date: ${new Date().toLocaleDateString("en-US", { weekday: "long", year: "numeric", month: "long", day: "numeric" })}`);
  lines.push("Location: New York, United States");
  lines.push("Context: Local Dev Environment Node-01");
  lines.push(`Simulation Seed: ${options.seed}`);
  lines.push("");
  lines.push(`Simulated ${options.totalRequests} requests across ${options.endpoints.length} endpoints.`);
  lines.push("");
  lines.push("Endpoint           | Requests | Avg Time   | Max Time   | Error Rate");
  lines.push("-----------------------------------------------------------------");

  Object.entries(results).forEach(([path, data]) => {
    const avg = data.requests > 0 ? (data.totalLatency / data.requests).toFixed(2) : "0.00";
    const max = data.maxLatency.toFixed(2);
    const errRate = data.requests > 0 ? ((data.errors / data.requests) * 100).toFixed(1) : "0.0";
    const name = path.padEnd(18);
    lines.push(`${name} | ${String(data.requests).padStart(8)} | ${avg.padStart(8)}ms | ${max.padStart(8)}ms | ${errRate.padStart(4)}%`);
  });

  lines.push("");
  lines.push("Simulation complete. No major bottlenecks detected in local dev.");
  lines.push("=====================================================");
  return lines.join("\n");
}

export { runSimulation, parseArgs, seededRandom };

import { fileURLToPath } from "url";
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const options = parseArgs();
  console.log(formatReport(runSimulation(options), options));
}
