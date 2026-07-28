---
title: Consensus Without a Leader
---

# Consensus without a leader

::: meta
Distributed Systems Reading Group · Week 7 · 2026-07-28 · Room 214
:::

Leaderless replication trades a single ordering authority for a quorum. The
question for today: what do we actually give up, and when is that trade worth it?

## The setup

Every replica accepts writes. A write is acknowledged once a quorum of replicas
has stored it; a read consults a quorum and reconciles conflicts. With `N`
replicas and quorum size `W` for writes and `R` for reads, overlap is guaranteed
when `W + R > N` — the classic condition for reading your own writes.

## What we give up

- **A total order.** Concurrent writes are ordered per-key, not globally.
- **Read-your-writes across clients** — only within the overlapping quorum.
- **Simple reasoning.** Conflict resolution (last-writer-wins, vector clocks,
  CRDTs) now lives in the application's mental model, not the database's.

## Open questions

- Does hinted handoff actually improve availability, or just hide unavailability?
- Where is the crossover point where a leader-based system is simpler *and* faster?
- Can we teach the conflict model without teaching vector clocks first?

## For next week

Read the Dynamo paper §4 and come with one workload where leaderless clearly wins.
