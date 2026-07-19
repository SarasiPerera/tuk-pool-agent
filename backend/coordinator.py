"""
DispatchCoordinator: the single "joint action" decision-maker for the
tuk-pooling system.

Framing:
  - Each waiting student is effectively an independent agent that has
    already committed to one action ("I want to go to Wijerama, and I'm
    willing to pool") the moment they join the queue.
  - The COORDINATOR then makes one joint decision -- dispatch now, or
    hold for a bit longer -- whose outcome (fare share, wait time)
    applies jointly to every student currently in the queue. This is
    the "joint action" in this system: one action, shared consequence
    across multiple agents.
  - We learn this dispatch/hold policy with tabular Q-learning trained
    on a simulated arrival process, rather than hand-coding a fixed
    threshold, so the trade-off between "wait for a cheaper split" and
    "don't make people wait too long" is learned from simulated reward,
    not guessed.

State:  (num_waiting capped at MAX_CAPACITY, oldest_wait_minutes capped at MAX_WAIT_BUCKET)
Action: "wait" | "dispatch"
Reward:
  - dispatch: -fare_per_student for that group size (120 / 60 / 40)
  - wait (while someone is queued): -WAIT_TICK_PENALTY, an ongoing small
    cost representing the group's collective discomfort of waiting one
    more minute. This is what makes "wait forever for a full tuk" a bad
    policy -- without an ongoing wait cost, waiting is "free" until the
    moment of dispatch and the agent learns to hoard for capacity no
    matter how long it takes, which isn't realistic.
"""

import random

MAX_CAPACITY = 3
MAX_WAIT_BUCKET = 8  # minutes, capped
FARE_FOR_GROUP_SIZE = {1: 120, 2: 60, 3: 40}
WAIT_TICK_BASE = 3       # base cost of waiting one more minute
WAIT_TICK_GROWTH = 4     # extra cost per minute already waited (growing impatience)


class DispatchCoordinator:
    def __init__(self):
        self.Q = {}
        for n in range(0, MAX_CAPACITY + 1):
            for w in range(0, MAX_WAIT_BUCKET + 1):
                self.Q[(n, w)] = {"wait": 0.0, "dispatch": 0.0}

    def _valid_actions(self, n):
        if n == 0:
            return ["wait"]
        if n >= MAX_CAPACITY:
            return ["dispatch"]
        return ["wait", "dispatch"]

    def train(self, episodes=20000, arrival_prob=0.35, alpha=0.2, gamma=0.9,
              epsilon=0.15, horizon=25):
        """Simulate many short episodes of a queue filling up with random
        arrivals, learning when to dispatch vs. hold."""
        for _ in range(episodes):
            n = 0
            oldest_wait = 0

            for _tick in range(horizon):
                state = (n, min(oldest_wait, MAX_WAIT_BUCKET))
                actions = self._valid_actions(n)

                if random.random() < epsilon:
                    action = random.choice(actions)
                else:
                    action = max(actions, key=lambda a: self.Q[state][a])

                if action == "dispatch":
                    group_size = n
                    fare_each = FARE_FOR_GROUP_SIZE[group_size]
                    reward = -fare_each
                    n = 0
                    oldest_wait = 0
                else:
                    # growing impatience: waiting one more minute costs more
                    # the longer the group has already been waiting
                    reward = -(WAIT_TICK_BASE + WAIT_TICK_GROWTH * oldest_wait) if n > 0 else 0.0
                    if n > 0:
                        oldest_wait += 1

                # simulate a new arrival this tick
                if n < MAX_CAPACITY and random.random() < arrival_prob:
                    n += 1

                next_state = (n, min(oldest_wait, MAX_WAIT_BUCKET))
                next_actions = self._valid_actions(n)
                best_next_q = max(self.Q[next_state][a] for a in next_actions)

                old_q = self.Q[state][action]
                self.Q[state][action] = old_q + alpha * (
                    reward + gamma * best_next_q - old_q
                )

    def decide(self, num_waiting: int, oldest_wait_minutes: float) -> str:
        n = min(num_waiting, MAX_CAPACITY)
        w = min(int(oldest_wait_minutes), MAX_WAIT_BUCKET)
        actions = self._valid_actions(n)
        state = (n, w)
        return max(actions, key=lambda a: self.Q[state][a])
