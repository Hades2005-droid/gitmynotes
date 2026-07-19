# Local Dev Simulations — Shadow Jing Garden 4.2

Headless simulations for testing core party-game mechanics without a browser.
Everything here is a **fictional 18+ simulation game**: local, deterministic,
no network, no media generation, no external calls.

## Available Simulations

### `run-4.2-game-simulation.js`
Models the central 4.2 systems:
- Harmony drain + restoration
- 4 matriarch character switching (1-4)
- Q/E ability cooldown tracking
- Active effect simulation (freeze, gravity, phase, etc.)
- Shard collection economy
- Mock "combat" pressure loop

```bash
node simulations/run-4.2-game-simulation.js            # random run
node simulations/run-4.2-game-simulation.js --seed=42  # reproducible run
```

### `clock-test.js`
Exercises the real absolute-frame timing module in `../src/game/clock.js`
(`GameClock`, `scheduleIn`, `processScheduledEvents`, `hasReached`,
`createExpiration`). Exits non-zero if the scheduled events don't all fire.

```bash
node simulations/clock-test.js
```

### `nyc-local-dev-simulator.js`
Synthetic local-dev performance report (no real requests are made).

```bash
node simulations/nyc-local-dev-simulator.js
node simulations/nyc-local-dev-simulator.js --requests=200 --seed=42 --json
node simulations/nyc-local-dev-simulator.js --endpoints=auth,users,healthz --requests=150
```

### `party-round.js` — the playable round (convergence)

Reads today's (or `--date`) Spacetime ledger archetype as the round's **turn
prompt**, binds an anchor matriarch, runs a bounded round, and prints a visible
**win/hold/lose** resolution. Supports restart via `--rounds=N`. The ledger table
is loaded from `../src/game/ledger.json`, which is exported from the canonical
Python codex (`python eden/app_index_codex.py --ledger-json …`) so the game and
codex never diverge.

```bash
node simulations/party-round.js                                   # today, 1 round
node simulations/party-round.js --date=2026-07-15 --seed=42 --rounds=3
node simulations/party-round.js --json                            # machine output
```

Regenerate the ledger after editing the Python codex:

```bash
python3 eden/app_index_codex.py --ledger-json eden/game/src/game/ledger.json
```

## Smoke test + tests (the playable vertical slice)

```bash
cd eden/game && npm run smoke   # all four sims, fixed seeds
cd eden/game && npm test        # node --test: 10 assertions (mechanics + round)
```

`npm run smoke` runs every sim with fixed seeds and fails if the clock slice
misfires. `party-round.js` is the convergence milestone: a complete short round
with a clear turn prompt, deterministic resolution, visible end state, and
restart — no external write.

## Future Ideas
- Stress-test specific ability combinations
- Harmony economy tuning experiments
- Monte Carlo balance runs
- Export simulation logs as JSON for analysis

These validate mechanics before touching any React/Canvas implementation.
