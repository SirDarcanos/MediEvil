'use strict';

// Observed horizontal movement, not facing. Owns its history and expiry so the
// arrow can disappear even while the next HTTP request is still pending.
class MovementTracker {
  constructor(onExpiry) {
    this.onExpiry = onExpiry;
    this.sample = null;
    this.direction = null;
    this.lastMovementAt = 0;
    this.expiryTimer = null;
  }

  clearDirection() {
    this.direction = null;
    clearTimeout(this.expiryTimer);
    this.expiryTimer = null;
  }

  directionAt(now) {
    return now - this.lastMovementAt > 250 ? null : this.direction;
  }

  track(sample, now) {
    const position = sample?.position;
    if (sample?.status !== 'live' || sample.source === 'snapshot' || !Array.isArray(position) ||
        position.length !== 3 || !position.every(Number.isFinite) || !Number.isInteger(sample.frame)) {
      this.sample = null;
      this.clearDirection();
      return;
    }
    const key = JSON.stringify([
      sample.epoch, sample.pid, sample.emulator, sample.level, sample.player_address, sample.state_address,
    ]);
    const previous = this.sample;
    this.sample = {key, frame: sample.frame, position: position.slice(), at: now};
    if (!previous || previous.key !== key || now < previous.at || now - previous.at > 500 ||
        sample.frame < previous.frame) {
      this.clearDirection();
      return;
    }
    const dx = position[0] - previous.position[0];
    const dz = position[2] - previous.position[2];
    const distance = Math.hypot(dx, dz);
    if (sample.frame === previous.frame) {
      if (distance) this.clearDirection();
      return; // Repeated HTTP samples are not a new movement observation.
    }
    if (distance < 1 || distance > 1024) {
      this.clearDirection();
      return;
    }
    this.direction = {x: dx / distance, y: -dz / distance};
    this.lastMovementAt = now;
    clearTimeout(this.expiryTimer);
    this.expiryTimer = setTimeout(() => {
      this.clearDirection();
      this.onExpiry();
    }, 251);
  }
}
