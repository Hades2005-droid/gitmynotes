#!/usr/bin/env node
/**
 * Clock System Test / Simulation
 *
 * Exercises the real absolute-frame timing module (GameClock + scheduler) in
 * ../src/game/clock.js. Deterministic and local — every frame advance is
 * explicit, so scheduled events fire in a reproducible order.
 *
 * Run with: node simulations/clock-test.js
 */

import {
  GameClock,
  scheduleIn,
  processScheduledEvents,
  hasReached,
  createExpiration,
} from "../src/game/clock.js";
import { fileURLToPath } from "url";

export function runClockTest(totalFrames = 70) {
  console.log("=== 4.2 GameClock + Scheduler Test ===\n");
  console.log("Starting simulation...\n");

  const clock = new GameClock();
  const fired = [];

  scheduleIn(clock, 10, "Makima Q ends", () => console.log("  \u2192 Freeze effect expired"));
  scheduleIn(clock, 25, "Seiko E harmony pulse", () => console.log("  \u2192 +Harmony from Seiko E"));
  scheduleIn(clock, 40, "Momo Phase Shift ends", () => console.log("  \u2192 Ghosting disabled"));
  scheduleIn(clock, 60, "Big lattice sync event", () => console.log("  \u2192 GLOBAL LATTICE PULSE"));

  // A duration marker to prove createExpiration works.
  const freeze = createExpiration(clock, 10);

  for (let i = 0; i < totalFrames; i++) {
    clock.advance();
    for (const label of processScheduledEvents(clock)) {
      fired.push(label);
      console.log(`[Frame ${clock.frame}] Executing scheduled event: ${label}`);
    }
    if (i % 15 === 0) {
      console.log(`[Frame ${clock.frame}] Status: ${clock._events.length} events remaining`);
    }
  }

  console.log("\nTest complete. Clock reached frame", clock.frame);
  console.log(`Freeze expired: ${freeze.isExpired(clock)} | reached frame 60: ${hasReached(clock, 60)}`);

  return { finalFrame: clock.frame, fired };
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const result = runClockTest();
  const expected = 4;
  if (result.fired.length !== expected) {
    console.error(`FAIL: expected ${expected} scheduled events to fire, got ${result.fired.length}`);
    process.exit(1);
  }
}
