# Debug Plan — generic template

Rule: **one hypothesis → one test → one saved output → one decision.**
Order steps **cheapest first** (2-min checks before 1-hr setups). Every step needs an **If YES** and an **If NO**.

```
TASK:          [Customer/System] [Ticket] – one-line OUTCOME (not a status)
PROBLEM:       What fails · where · since when · how to reproduce
WHY:           Who is blocked / what is at stake
SUSPECTED FIX: What I think the fix is (confidence: low/med/high) → test it as Step 1
DONE WHEN:     [Verified working] + [root cause written in Jira] + [reply sent]
TIMEBOX:       total __ h | Deadline: __ | Escalate to __ if not isolated by: __
EVIDENCE:      folder/link where every log & screenshot goes

STEP n – Hypothesis: "__ is the cause"            (__ min)
  Test:    exact action / command
  Output:  what evidence is saved, and where
  If YES → next step / fix / done
  If NO  → next step / rule out

FIRST ACTION:  ≤10-min physical step I can do right now
STATUS:        [where I stopped] → [next action] → [when]

CLOSE-OUT:     Root cause · Fix/workaround · Jira comment · Customer reply · Prevent recurrence
```

Quality checks before you start:
- [ ] Title says the outcome, not "done"/"issue"
- [ ] Every step has If YES and If NO (no dead ends)
- [ ] Every step saves evidence
- [ ] Step timeboxes add up to ≤ total timebox
- [ ] There is a named escalation point
- [ ] DONE WHEN includes what you send (Jira / reply)
- [ ] FIRST ACTION fits in 10 minutes
