---
theme: speaker
title: "Leaderless consensus — speaker notes"
subtitle: "Reading group, 12 minutes"
author: "Prepared for the presenter"
date: "2026-07-28"
---

# How to read these notes

One page per slide, in the same 16:9 shape as the deck, so the page you are on
and the slide the room is looking at stay in step. Nothing here is a script.
Each page says what to stress, what number to land, and what to leave out.

**Timing.** Twelve minutes over eight content slides, so about ninety seconds
each. Do not spread it evenly: slide 3 carries the result and deserves twice
what slide 2 gets.

# Slide 1 · Title (≈ 20 s)

**Core idea:** name the group, name the question, move on.

**Stress:** the question is when leaderless replication is worth its cost, not
whether it works.

**Do not:** read the author list.

# Slide 2 · The quorum condition (≈ 60 s)

**Core idea:** `W + R > N` is the whole mechanism.

**Stress:**

- Write it on the board if there is one. People remember the inequality.
- Give the concrete case: five replicas, write to three, read from three, and
  the two quorums always share a replica.

**Do not:** derive it. The audience either knows it or will look it up.

# Slide 3 · What it costs (≈ 90 s)

**Core idea:** the cost is reconciliation, and it lands on the reader.

**Stress:** the number to land is the tail latency, not the median. Pause after
saying it.

**Do not:** promise that vector clocks solve this.
