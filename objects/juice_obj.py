"""Phase 1 juice helpers: catch particles, screen shake, screen flash.

Feel only — no rule changes. Everything here is drawn with plain
rects/circles on pygame Surfaces (no new assets) and is safe to run
headless (dummy video/audio drivers).
"""

import math
import random

import pygame

# Catch-burst particles live 0.4s (roadmap: "crumb bursts, 0.4s life").
PARTICLE_LIFE = 0.4
PARTICLE_COUNT = 16
PARTICLE_GRAVITY = 1400.0  # px/s^2 — snappy fall, gone in 0.4s anyway


class ParticleBurst:
    """One 0.4s crumb burst of rects/circles at a catch point."""

    def __init__(self, x, y, color, count=PARTICLE_COUNT):
        self.particles = []
        for _ in range(count):
            ang = random.uniform(0, math.tau)
            speed = random.uniform(120, 420)
            size = random.randint(3, 8)
            circle = random.random() < 0.5  # mix of rects and circles
            self.particles.append(
                {
                    'x': float(x),
                    'y': float(y),
                    'vx': math.cos(ang) * speed,
                    'vy': math.sin(ang) * speed - 160.0,  # pop upward first
                    'life': PARTICLE_LIFE,
                    'size': size,
                    'circle': circle,
                    'color': color,
                }
            )

    def update(self, dt):
        alive = []
        for p in self.particles:
            p['life'] -= dt
            if p['life'] <= 0:
                continue
            p['vy'] += PARTICLE_GRAVITY * dt
            p['x'] += p['vx'] * dt
            p['y'] += p['vy'] * dt
            alive.append(p)
        self.particles = alive

    @property
    def dead(self):
        return not self.particles

    def draw(self, surf):
        for p in self.particles:
            alpha = max(0.0, min(1.0, p['life'] / PARTICLE_LIFE))
            # fade by shrinking — avoids per-particle alpha surfaces
            s = max(1, int(p['size'] * alpha))
            if p['circle']:
                pygame.draw.circle(surf, p['color'], (int(p['x']), int(p['y'])), s)
            else:
                r = pygame.Rect(int(p['x']) - s // 2, int(p['y']) - s // 2, s, s)
                surf.fill(p['color'], r)


class JuiceState:
    """Screen shake + full-screen flash, driven by simple timers."""

    def __init__(self):
        self.shake_t = 0.0
        self.shake_dur = 0.0
        self.shake_mag = 0
        self.flash_t = 0.0
        self.flash_dur = 0.0
        self.flash_color = (255, 0, 0)

    def shake(self, dur=0.35, mag=14):
        self.shake_t = dur
        self.shake_dur = dur
        self.shake_mag = mag

    def flash(self, color, dur=0.25):
        self.flash_color = color
        self.flash_t = dur
        self.flash_dur = dur

    def update(self, dt):
        if self.shake_t > 0:
            self.shake_t = max(0.0, self.shake_t - dt)
        if self.flash_t > 0:
            self.flash_t = max(0.0, self.flash_t - dt)

    def offset(self):
        """Current shake offset in px; (0, 0) when idle. Decays with time."""
        if self.shake_t <= 0 or self.shake_dur <= 0:
            return (0, 0)
        k = self.shake_t / self.shake_dur  # 1 -> 0
        m = self.shake_mag * k
        return (
            int(random.uniform(-m, m)),
            int(random.uniform(-m, m)),
        )

    def draw_flash(self, surf):
        """Translucent full-screen overlay while a flash is active."""
        if self.flash_t <= 0 or self.flash_dur <= 0:
            return
        try:
            alpha = int(140 * (self.flash_t / self.flash_dur))
            overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
            overlay.fill((*self.flash_color, alpha))
            surf.blit(overlay, (0, 0))
        except pygame.error:
            pass  # headless surface hiccup — flash is cosmetic
