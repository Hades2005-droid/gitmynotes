/**
 * 4.2 Shadow Jing Garden — GameClock + frame scheduler.
 *
 * Absolute-frame timing for the fictional party-game sim. Deterministic and
 * local: a clock is just a monotonically increasing frame counter, and events
 * are scheduled against absolute frame targets. No wall-clock, no timers, no
 * network — every advance is explicit, which keeps simulations reproducible.
 */

export class GameClock {
  constructor(startFrame = 0) {
    this.frame = startFrame;
    this._events = [];
  }

  /** Advance the clock by one (or more) frames. Returns the new frame index. */
  advance(frames = 1) {
    this.frame += frames;
    return this.frame;
  }
}

/** Schedule a callback `delay` frames from now. Returns the event handle. */
export function scheduleIn(clock, delay, label, callback) {
  return scheduleAtFrame(clock, clock.frame + delay, label, callback);
}

/** Schedule a callback at an absolute frame target. Returns the event handle. */
export function scheduleAtFrame(clock, targetFrame, label, callback) {
  const event = { target: targetFrame, label, callback, done: false };
  clock._events.push(event);
  return event;
}

/**
 * Run every scheduled event whose target frame has been reached, in target
 * order. Executed events are removed. Returns the list of fired event labels.
 */
export function processScheduledEvents(clock) {
  const fired = [];
  clock._events.sort((a, b) => a.target - b.target);
  for (const event of clock._events) {
    if (!event.done && event.target <= clock.frame) {
      event.done = true;
      fired.push(event.label);
      if (typeof event.callback === 'function') event.callback(clock.frame, event.label);
    }
  }
  clock._events = clock._events.filter((e) => !e.done);
  return fired;
}

/** True once the clock has reached (or passed) the given absolute frame. */
export function hasReached(clock, targetFrame) {
  return clock.frame >= targetFrame;
}

/**
 * Create an expiration marker `duration` frames ahead. `isExpired(clock)` flips
 * true once the clock reaches it — handy for ability/effect durations.
 */
export function createExpiration(clock, duration) {
  const expiresAt = clock.frame + duration;
  return {
    expiresAt,
    isExpired: (c) => c.frame >= expiresAt,
    framesRemaining: (c) => Math.max(0, expiresAt - c.frame),
  };
}
