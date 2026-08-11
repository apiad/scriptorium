---
theme: deck
title: Shipping Faster Without Breaking Things
subtitle: A field guide to continuous delivery
author: Northwind Platform Team
date: July 2026
---

::: toc {title="Agenda"}
:::

# The problem

## We ship slowly, and we ship scared

- Releases are big, rare, and mostly manual
- Every deploy is an event — so every deploy is treated as a risk
- The fear compounds: rare releases mean bigger batches, which mean more risk

## The cost, in numbers

::: kpi-dash three
::: kpi accent {label="Deploy frequency" value="1 / wk" sub="leaders ship 10+/day"}
:::
::: kpi amber {label="Lead time" value="12 days" sub="commit to production"}
:::
::: kpi rose {label="Change failure" value="28%" sub="of deploys need a fix"}
:::
:::

# The shift

## Small batches change everything

Continuous delivery is not a tool you buy — it is a decision about batch size.
Ship smaller and ship more often, and each change carries less risk simply
because there is less of it to go wrong.

::: finding emerald {icon=1 title="Smaller is safer"}
A one-line change that ships in an hour is trivially easy to reason about and to
roll back. A thousand-line change that ships once a month is neither.
:::

## What it actually takes

- A pipeline that runs on every commit, no exceptions
- A test suite you trust enough to gate a release on
- Feature flags, so that "deployed" and "released" come apart

::: statement
Small changes, shipped often, **compound**.
:::

# Where to start

## One week, one change

Pick the smallest service you own. Put one test in front of it. Deploy it the
moment the pipeline is green. Do it again tomorrow. The habit is the product —
the tooling just makes the habit cheap.

::: closing {contact="platform@northwind.example"}
Ship small. Ship often.
:::
