# .ai/steering/product.md

# MetroIsJustABus — Product Vision

## Value Proposition
MetroIsJustABus is a distributed software system for an urban bus network. It gives passengers up-to-date information on lines, stops, schedules and disruptions, lets them buy and validate tickets, and notifies them when something they follow changes. It gives operational staff the tools to run the network, tickets and disruptions.

## The Problem We Solve
1. Passengers need one reliable place to see lines, stops, schedules and trips, with known changes to normal operation already applied
2. Delays, cancellations and diversions reach passengers late or not at all
3. Ticket purchase and validation must be correct: a ticket is never issued twice, and a journey is never spent twice, even with retries or concurrent use
4. Staff have no view of ticket usage, boardings and crowding
5. A failure in one part (for example notifications) must not take the whole service down

## Solution
- Public consultation of the network, schedules and trips, with disruptions applied (no account needed)
- Passenger accounts with ticket purchase, ticket list and validation history
- Ticket validation at the stop entrance: the validator device submits ticket, validator and time, and the system accepts or rejects the attempt, returning a reason on every rejection
- Staff back-office for network, schedules, ticket types and disruptions
- Subscriptions to a line, stop or trip, with notification preferences and an in-app inbox
- Estimated occupancy and crowding levels derived from boardings
- Independent, separately deployable components that talk through explicit APIs and events, and tolerate failures, duplicates and retries

## What This Product Is NOT
- Not a journey planner: no origin-to-destination routing
- Not a real-time vehicle tracking system: no GPS feed. Delays and cancellations are registered by staff as disruptions
- Does not measure real onboard occupancy: alighting is not recorded, so occupancy is an estimate and over-capacity is never claimed or detected
- Not a payment platform: payment is simulated, with no real payment processing
- No refunds and no ticket transfers
- Not a native mobile app: it is a responsive web application
- Not one application behind one REST API: a single backend does not meet the distributed-system requirement
- No per-line validation statistics: validation happens at the stop entrance, tickets are valid on all lines, and validation requests carry no line or trip

## Audience
1. **Visitors**: unauthenticated users who consult public network information
2. **Passengers**: registered users who buy tickets, follow lines, stops and trips, and receive notifications
3. **Operational staff**: maintain the network, schedules, ticket types and disruptions, and monitor ticket usage and occupancy. One role initially, designed so it can be split later (for example dispatcher, ticket manager)
4. **Validators**: fixed devices at stop or station entrances. They are system actors, not people. Simulators stand in for them in tests and demos

## Core Features (MVP)
1. Network and schedule consultation: lines, stops, ordered stops per line, schedule variants by date, departure boards, trip details
2. Disruptions applied to passenger views: trip states (on time, delayed, cancelled, diverted), scoped to a line, stops, trips or periods
3. Accounts and roles: sign-up, authentication, and enforced separation of visitor, passenger and staff
4. Tickets: multiple ticket types, purchase with simulated payment, lifecycle states, and a ticket list per passenger
5. Ticket validation: validity decision, recorded validations, concurrency-safe, and idempotent
6. Occupancy: capacity per trip and estimated occupancy from boardings, with crowding levels for passengers and indicators for staff
7. Subscriptions and notifications: subscribe to a line, stop or trip, set preferences, deduplicated delivery, in-app inbox and a sandboxed e-mail channel
8. Staff back-office: network and schedule maintenance, ticket types, disruption management, and ticket usage queries
9. Resilience: no duplicate tickets, validations or notifications. Events survive a component outage and are processed after recovery. Passengers see a visible degraded mode when information is stale

## Future Features (v2+)
- Scheduled future-dated network changes
- Staff sub-roles
- Route planning between origin and destination
- Real vehicle tracking
- Passenger counting, to measure real onboard occupancy
- Real payment provider
- Refunds and ticket transfers
- Portuguese interface (the first version is English with externalised text)
- Native mobile apps

## Success Metrics
Targets are proposed. The project statement gives none, and the team must confirm them (see the requirements specification, section 3.5).
- Availability of the production core (consultation and validation) of at least 99.5% per month
- Read requests for lines, stops, schedules and departures: p95 under 500 ms
- Ticket validation: p95 under 1 s
- Notification issued within 30 s of the triggering event under nominal load
- Zero duplicate tickets, validations or notifications in failure-injection tests
- Consultation and unrelated functions keep working when the notification service is down
