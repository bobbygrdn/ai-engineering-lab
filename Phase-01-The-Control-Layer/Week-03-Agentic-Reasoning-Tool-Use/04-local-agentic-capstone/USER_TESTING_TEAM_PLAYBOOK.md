# User Testing Team Playbook (Internal)

This document is internal-only and should not be shared directly with participants.

## Goal

Validate that users can complete the core authenticated support flow end-to-end:

1. Register/login
2. Submit a support message
3. Receive streaming response
4. Understand session-health status and session-expiry behavior
5. Recover from auth/session failures

## Scope

In scope:

- Frontend auth UX and messaging
- Session-health badge behavior
- Streaming request flow (`/api/handle`)
- Logout-all flow

Out of scope:

- Deep model quality benchmarking
- Production performance/load testing
- Security penetration testing

## Environment Setup

Run backend:

```bash
cd backend
./venv/Scripts/python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000
```

Run frontend:

```bash
cd frontend
npm run dev
```

Open app:

- `http://localhost:5173`

Recommended facilitator setup:

- Keep browser DevTools open (Console + Network)
- Keep backend terminal visible for auth/tool logs

## Participant Mix

Target 5-8 participants:

- 2-3 technical users
- 2-3 non-technical users
- Optional 1-2 mixed-role stakeholders

## Facilitator Checklist

Before session:

- [ ] Backend running on port 8000
- [ ] Frontend running on port 5173
- [ ] Fresh test account strategy ready
- [ ] Note-taking template opened

During session:

- [ ] Do not assist unless participant is blocked >60s
- [ ] Capture exact confusion points and wording
- [ ] Record any console/network/backend errors

After session:

- [ ] Mark task outcomes
- [ ] Assign severity to issues
- [ ] Add reproduction steps for each failure

## Data Capture Template

Use this table per participant:

| Participant | Task                         | Completed (Y/N) | Time (s) | Errors Observed | User Confusion Notes |
| ----------- | ---------------------------- | --------------- | -------: | --------------- | -------------------- |
| P1          | Register                     |                 |          |                 |                      |
| P1          | Login                        |                 |          |                 |                      |
| P1          | Stream response              |                 |          |                 |                      |
| P1          | Session badge interpretation |                 |          |                 |                      |
| P1          | Session-expiry recovery      |                 |          |                 |                      |
| P1          | Logout-all validation        |                 |          |                 |                      |

Satisfaction quick score:

- "How confident are you that you can recover if your session expires?" (1-5)
- "How clear was the session badge?" (1-5)
- "How easy was the overall flow?" (1-5)

## Severity Rubric

- Critical: Blocks primary flow or causes unsafe state
- High: Major confusion or repeated failure without guidance
- Medium: Recoverable issue with noticeable friction
- Low: Minor UX polish or wording issue

## Exit Criteria for This Phase

Recommend passing this phase when all are true:

- > =90% task completion on core flow (register/login/submit/recover)
- 0 critical auth/session-flow defects
- 0 unrecoverable UI states
- Session failure messaging understood by >=80% participants
- Average ease score >=4/5

## Issue Report Format

For each issue, capture:

1. Title
2. Severity
3. Reproduction steps
4. Expected behavior
5. Actual behavior
6. Evidence (screenshot/log line)
7. Suggested fix

## Fast Regression After Fixes

```bash
cd frontend
npx vitest run
```

```bash
cd backend
./venv/Scripts/python -m pytest -q
```

Then repeat 1-2 participant smoke sessions.
