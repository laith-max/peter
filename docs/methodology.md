# Methodology

## Field Test Site Selection

AI monitoring devices were deployed across four ECEC field test centres in
New South Wales, selected to represent variation in service size (15–120
enrolled children), NQF Quality Area performance profiles, staffing models,
and governance structures. The four sites comprised:

| Site label     | Service size band      | Setting     |
|----------------|------------------------|-------------|
| Urban Large    | High enrolment (~120)  | Metro       |
| Urban Small    | Low enrolment (~15–30) | Metro       |
| Regional Large | High enrolment         | Non-metro   |
| Regional Small | Low enrolment          | Non-metro   |

This 2 × 2 design (urban/regional × large/small) was itself a research
judgment about which variables were expected to have predictive relevance
for the outcomes under study. Geography was treated as a proxy for
workforce availability, family demographics, and access to allied-health
support; service size was treated as a proxy for room configuration
complexity, ratio pressure, and management overhead. Sites were further
balanced — not matched — across NQF Quality Area ratings so that the
sample contained both "Meeting" and "Exceeding" services, and across
governance structures (private for-profit, not-for-profit, community-
managed) so that operational variance was not collapsed onto a single
ownership model.

## Data Sources

Devices captured multi-modal operational data within applicable privacy
constraints (see [`data-acquisition-protocol.md`](./data-acquisition-protocol.md)).
A governance dataset was assembled from:

- **NQF assessment records** — most recent rating reports and any
  conditional notices issued by the regulatory authority.
- **Staff rosters** — rostered vs. worked hours, qualification mix,
  educator-to-child ratios per room per 15-minute interval.
- **Incident logs** — notifiable incidents under Regulation 176 plus
  centre-level minor incident records where available.
- **Room configuration data** — floor plans, room-to-age-group
  assignments, transition windows, and indoor/outdoor scheduling.

Data acquisition and pre-processing protocols were documented prior to
collection; no exploratory pulls were taken before the protocol was
ratified by the project's ethics committee.

## On-Device Processing

On-device processing was performed on NVIDIA Jetson Orin Nano Super
edge computing hardware. Architecture and rationale are documented in
[`jetson-processing.md`](./jetson-processing.md); device-side logging,
retention, and privacy controls are documented in the
[`jetson-logging/`](../jetson-logging/) module.
