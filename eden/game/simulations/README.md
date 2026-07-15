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

## Smoke test (the playable vertical slice)

```bash
cd eden/game && npm run smoke
```

Runs all three sims with fixed seeds and fails the process if the clock slice
misfires. This is the locally runnable vertical slice for the evolution loop.

## Future Ideas
- Stress-test specific ability combinations
- Harmony economy tuning experiments
- Monte Carlo balance runs
- Export simulation logs as JSON for analysis

These validate mechanics before touching any React/Canvas implementation.
