#!/usr/bin/env node
/**
 * 4.2 Shadow Jing Garden — playable party round (headless).
 *
 * The convergence slice: reads today's (or --date) Spacetime ledger archetype as
 * the round's turn prompt, binds an anchor matriarch, runs a bounded round, and
 * prints a visible end state + resolution. Supports restart via --rounds=N.
 * Local + deterministic (fixed --seed). No network, no media, no external writes.
 *
 * Usage:
 *   node simulations/party-round.js
 *   node simulations/party-round.js --date=2026-07-15 --seed=42 --rounds=3
 *   node simulations/party-round.js --json
 */

import { startRound, playRounds } from "../src/game/round.js";
import { fileURLToPath } from "url";

function parseArgs() {
  const o = { date: undefined, seed: 42, rounds: 1, json: false, durationMs: 12000, bridge: false };
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith("--date=")) o.date = new Date(arg.split("=")[1] + "T12:00:00Z");
    if (arg.startsWith("--seed=")) o.seed = parseInt(arg.split("=")[1], 10);
    if (arg.startsWith("--rounds=")) o.rounds = parseInt(arg.split("=")[1], 10);
    if (arg.startsWith("--duration=")) o.durationMs = parseInt(arg.split("=")[1], 10) * 1000;
    if (arg === "--json") o.json = true;
    // Step onto the bridge to the outer world at the end of the round. Optional
    // "=action" picks the external action; without --confirm it stays a dry-run.
    if (arg === "--cross-bridge") o.bridge = { action: "grok_send", confirmToken: null };
    if (arg.startsWith("--cross-bridge=")) o.bridge = { action: arg.split("=")[1], confirmToken: null };
  }
  if (!o.date) o.date = new Date();
  return o;
}

function printRound(r, idx) {
  console.log(`\n--- Round ${idx + 1} :: ${r.turnPrompt.date} ---`);
  console.log(`Turn prompt (Micro ${r.turnPrompt.micro.raw}->${r.turnPrompt.micro.reduced}): ` +
    `${r.turnPrompt.micro.name} — ${r.turnPrompt.micro.flavor}`);
  console.log(`External (Macro ${r.turnPrompt.macro.raw}->${r.turnPrompt.macro.reduced}): ` +
    `${r.turnPrompt.macro.name}`);
  console.log(`Anchor matriarch: ${r.anchor.name} (${r.anchor.glyph})`);
  console.log(`Final harmony: ${r.outcome.finalHarmony}% | shards: ${r.outcome.shards} | ` +
    `casts: ${r.outcome.casts} | threshold: ${r.threshold}`);
  console.log(`>>> RESOLUTION: ${r.resolution.toUpperCase()}`);
  if (r.ending) {
    if (r.ending.side === "external" && r.ending.dryRun) {
      console.log(`>>> BRIDGE (${r.ending.action}): closed door -> ASUNA 0-POINT CHAMBER ` +
        `(dry-run, nothing crossed; per-action confirm required)`);
    } else if (r.ending.side === "external") {
      console.log(`>>> BRIDGE (${r.ending.action}): confirmed -> defer write to an approved runtime ` +
        `(the game performs no write)`);
    } else {
      console.log(`>>> BRIDGE (${r.ending.action}): internal open door (auto)`);
    }
  }
}

function main() {
  const o = parseArgs();
  console.log("=== 4.2 Shadow Jing Garden — Party Round ===");

  if (o.rounds === 1) {
    const r = startRound({ date: o.date, seed: o.seed, durationMs: o.durationMs, bridge: o.bridge });
    if (o.json) {
      console.log(JSON.stringify(r, null, 2));
    } else {
      printRound(r, 0);
      console.log("\nRestart with:  node simulations/party-round.js --rounds=3");
      console.log("Bridge ending: node simulations/party-round.js --cross-bridge");
    }
    return;
  }

  const { rounds, tally } = playRounds({ date: o.date, seed: o.seed, rounds: o.rounds, durationMs: o.durationMs });
  if (o.json) {
    console.log(JSON.stringify({ rounds, tally }, null, 2));
    return;
  }
  rounds.forEach(printRound);
  console.log(`\n=== Session tally: ${JSON.stringify(tally)} ===`);
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  main();
}
