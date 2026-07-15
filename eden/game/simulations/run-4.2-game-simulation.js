#!/usr/bin/env node
/**
 * 4.2 Shadow Jing Garden — Local Headless Game Simulation (fictional 18+ sim).
 *
 * Simulates core party-game mechanics with zero network / media / external I/O:
 * - Harmony economy (drain over time + restoration from abilities/shards)
 * - Character switching (1-4 matriarch archetypes)
 * - Q/E ability cooldowns and basic effects
 * - Shard collection
 * - Simple "combat" loop with mock enemy pressure
 *
 * Run with: node simulations/run-4.2-game-simulation.js
 *
 * `--seed=<n>` makes the run deterministic (useful for tests/balance sweeps).
 */

const CHARACTERS = {
  1: { name: "Makima", glyph: "\u2295", hue: 0, qCooldown: 8000, eCooldown: 12000, harmonyRestore: 25 },
  2: { name: "Seiko",  glyph: "\u2609", hue: 30, qCooldown: 6000, eCooldown: 15000, harmonyRestore: 35 },
  3: { name: "Kaguya", glyph: "\u263e", hue: 270, qCooldown: 7000, eCooldown: 10000, harmonyRestore: 20 },
  4: { name: "Momo",   glyph: "\u2726", hue: 200, qCooldown: 5000, eCooldown: 9000, harmonyRestore: 18 },
};

// Optional seeded RNG so simulations are reproducible when --seed is passed.
function makeRng(seed) {
  if (seed === undefined) return Math.random;
  let s = seed >>> 0;
  return () => {
    s = (s * 9301 + 49297) % 233280;
    return s / 233280;
  };
}

class GameSimulation {
  constructor(rng = Math.random) {
    this.rng = rng;
    this.time = 0;                    // ms
    this.harmony = 100;               // 0-100
    this.currentChar = 1;
    this.cooldowns = { 1: { q: 0, e: 0 }, 2: { q: 0, e: 0 }, 3: { q: 0, e: 0 }, 4: { q: 0, e: 0 } };
    this.activeEffects = [];
    this.shards = 0;
    this.totalCasts = 0;
    this.peakEffects = 0;
    this.logs = [];
  }

  log(msg) {
    this.logs.push(`[${(this.time / 1000).toFixed(1)}s] ${msg}`);
    if (this.logs.length > 50) this.logs.shift();
  }

  tick(deltaMs = 100) {
    this.time += deltaMs;

    const pressure = 0.8 + (this.time / 60000) * 0.4;
    this.harmony = Math.max(0, this.harmony - pressure * (deltaMs / 100));

    for (const char of [1, 2, 3, 4]) {
      if (this.cooldowns[char].q > 0) this.cooldowns[char].q = Math.max(0, this.cooldowns[char].q - deltaMs);
      if (this.cooldowns[char].e > 0) this.cooldowns[char].e = Math.max(0, this.cooldowns[char].e - deltaMs);
    }

    this.activeEffects = this.activeEffects.filter((e) => {
      e.remaining -= deltaMs;
      return e.remaining > 0;
    });

    if (this.rng() < 0.12) {
      const gain = 8 + this.rng() * 12;
      this.shards += gain;
      this.harmony = Math.min(100, this.harmony + gain * 0.6);
      this.log(`\u25c6 Collected shard cluster (+${gain.toFixed(0)} harmony)`);
    }

    if (this.rng() < 0.18) {
      this.attemptCast(this.rng() < 0.55 ? "q" : "e");
    }

    if (this.rng() < 0.07) {
      const newChar = 1 + Math.floor(this.rng() * 4);
      if (newChar !== this.currentChar) {
        this.currentChar = newChar;
        this.log(`\u2192 Switched to ${CHARACTERS[this.currentChar].name}`);
      }
    }

    if (this.activeEffects.length > this.peakEffects) this.peakEffects = this.activeEffects.length;
  }

  attemptCast(slot) {
    const char = this.currentChar;
    const cd = this.cooldowns[char][slot];
    const charData = CHARACTERS[char];

    if (cd > 0) return;

    const cooldownTime = slot === "q" ? charData.qCooldown : charData.eCooldown;
    this.cooldowns[char][slot] = cooldownTime;

    let effectName = "";
    if (char === 1) effectName = slot === "q" ? "Absolute Freeze" : "Decree Slow";
    if (char === 2) effectName = slot === "q" ? "Heavy Sink" : "Gravity Anchor";
    if (char === 3) effectName = slot === "q" ? "Lunar Pulse" : "Quantum Insight";
    if (char === 4) effectName = slot === "q" ? "Phase Shift" : "Friction Dash";

    const duration = slot === "q" ? 1800 : 3200;
    this.activeEffects.push({ char, name: effectName, remaining: duration, strength: slot === "q" ? 1.0 : 0.7 });

    this.harmony = Math.min(100, this.harmony + charData.harmonyRestore);
    this.totalCasts++;

    this.log(`${slot.toUpperCase()} cast: ${charData.name} - ${effectName} (+${charData.harmonyRestore} harmony)`);
  }

  getStatus() {
    const charData = CHARACTERS[this.currentChar];
    return {
      time: (this.time / 1000).toFixed(1),
      harmony: this.harmony.toFixed(1),
      char: `${charData.name} (${charData.glyph})`,
      shards: Math.floor(this.shards),
      effects: this.activeEffects.map((e) => `${e.name} (${(e.remaining / 1000).toFixed(1)}s)`).join(" | ") || "none",
      casts: this.totalCasts,
    };
  }

  run(durationMs = 60000, tickMs = 120) {
    console.log("=== 4.2 Shadow Jing Garden Headless Simulation ===");
    console.log(`Running for ${durationMs / 1000} seconds...\n`);

    const startHarmony = this.harmony;

    while (this.time < durationMs) {
      this.tick(tickMs);
      if (this.time % 5000 < tickMs) {
        const status = this.getStatus();
        console.log(`[${status.time}s] Harmony: ${status.harmony}% | ${status.char} | Shards: ${status.shards} | Effects: ${status.effects}`);
      }
    }

    const endStatus = this.getStatus();
    console.log("\n=== Simulation Complete ===");
    console.log(`Final Harmony: ${endStatus.harmony}% (started at ${startHarmony}%)`);
    console.log(`Total Shards Collected: ${Math.floor(this.shards)}`);
    console.log(`Total Ability Casts: ${this.totalCasts}`);
    console.log(`Peak Active Effects at once: ${this.peakEffects}`);

    return {
      finalHarmony: parseFloat(endStatus.harmony),
      shards: Math.floor(this.shards),
      casts: this.totalCasts,
      peakEffects: this.peakEffects,
      duration: durationMs / 1000,
    };
  }
}

// Parse an optional --seed for reproducible runs.
function parseSeed() {
  for (const arg of process.argv.slice(2)) {
    if (arg.startsWith("--seed=")) return parseInt(arg.split("=")[1], 10);
  }
  return undefined;
}

export { CHARACTERS, GameSimulation, makeRng };

// Run only when invoked directly (so tests can import without side effects).
import { fileURLToPath } from "url";
if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const sim = new GameSimulation(makeRng(parseSeed()));
  const result = sim.run(45000);
  console.log("\nResult object for further analysis:", result);
}
