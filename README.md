# USJ → Wijerama Tuk Pooling (Multi-Agent Joint Dispatch)

A live ride-pooling app for the USJ → Wijerama tuk route. Solo fare is
Rs 120; if students share, the fare splits evenly (Rs 60 for 2, Rs 40
for 3 - max capacity of a three-wheeler).

## The multi-agent / joint action framing

- Each student who requests a ride is effectively an independent agent:
  they've already decided "I want to go, and I'm open to sharing."
- The **DispatchCoordinator** is the agent that makes the interesting
  decision: for the whole group currently waiting, should it **dispatch
  now** or **hold a bit longer** hoping another student joins and the
  fare splits further? That decision applies jointly to everyone in the
  queue at that moment : one action, shared consequence across multiple
  agents, which is exactly what "joint action" means in a multi-agent
  system.
- Rather than hand-coding a fixed rule ("always wait for 3"), this
  policy is **learned with tabular Q-learning**, trained on a simulated
  random-arrival process. The reward trades off:
  - cheaper fare for a bigger group, vs.
  - a **growing impatience cost** the longer people are made to wait
    (see `coordinator.py` for the exact reward shaping - this was the
    key design decision: without an ongoing cost of waiting, the
    learned policy just hoards for a full tuk forever, which isn't
    realistic).
- The result is a genuine threshold policy: e.g. with 2 people waiting,
  it holds for a while hoping for a 3rd, but gives up and dispatches
  sooner than it would for 1 person waiting - because the marginal
  saving (60 → 40) is smaller than the saving of going from 1 → 2
  (120 → 60).

## Project structure

```
backend/
  coordinator.py     # Q-learning dispatch policy (wait vs. dispatch)
  queue_manager.py    # live in-memory queue, applies the policy every tick
  main.py             # FastAPI app: serves the frontend AND /api/* routes
  static/index.html   # the frontend (served by FastAPI itself)
  requirements.txt
  Procfile            # tells Render how to start the app
```

## Running it locally

```
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open **http://localhost:8000** - frontend and API are served from
the same app, one URL, no separate frontend server needed.

## Deploying it (for usability testing with real students)

Vercel isn't a good fit here - its serverless functions are stateless
and short-lived, and this app needs a persistent in-memory queue plus
a background loop that ticks every 15 seconds. Serverless platforms
generally can't do that (queues/background processing = "serverless is
out").

**Render** is the right tool: it runs your app as one long-running
process, exactly like running it locally, just on a public URL.

1. Push this `backend/` folder to a GitHub repo (Render deploys from Git).
2. Go to [render.com](https://render.com) → sign up (no card needed) →
   **New +** → **Web Service** → connect your repo.
3. Configure:
   - **Root directory:** `backend` (if the repo root isn't already `backend/`)
   - **Environment:** Python 3
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
     (Render auto-detects the `Procfile` too, so this is usually filled in for you.)
4. Deploy. You'll get a URL like `https://your-app-name.onrender.com` -
   share that directly with students for usability testing.

**Free tier heads-up:** Render's free web services spin down after a
period of inactivity and take ~30-60 seconds to "wake up" on the next
request. Fine for a course demo/usability test where you tell testers
"give it a moment to load first time"; not something you'd want for a
production app people rely on daily.

## Key parameters to know for your report (`coordinator.py`)

- `MAX_CAPACITY = 3` — tuk seats
- `FARE_FOR_GROUP_SIZE = {1: 120, 2: 60, 3: 40}`
- `WAIT_TICK_BASE` / `WAIT_TICK_GROWTH` - control how quickly impatience
  grows the longer people wait; tune these and re-run the sanity check
  below to see the policy shift.
- `HARD_WAIT_CAP_MINUTES` (in `queue_manager.py`) - a safety net that
  forces a dispatch after 8 minutes regardless of the learned policy,
  so no one is ever stuck waiting indefinitely if the policy is wrong
  in some edge case.

To inspect the learned policy directly (useful for a report table or
plot):

```python
from coordinator import DispatchCoordinator, MAX_CAPACITY, MAX_WAIT_BUCKET
c = DispatchCoordinator()
c.train(episodes=40000)
for n in range(MAX_CAPACITY + 1):
    print(n, [c.decide(n, w) for w in range(MAX_WAIT_BUCKET + 1)])
```

## Ideas for extending

- Track each waiting student's own wait time individually instead of
  using the oldest student's wait as a proxy for the group (better
  credit assignment).
- Add a second route/direction (e.g. Wijerama → USJ mornings) as a
  second coordinator instance.
- This is a natural stepping stone toward the mode-choice app (bus vs.
  tuk vs. walk) you built earlier - you could combine them so the
  "tuk" option in that system is actually powered by this live pooling
  logic instead of a flat simulated fare.
