# Knowledge Card: statistics/discrete-event-simulation

## Tags
- discrete system
- discrete-event simulation
- event simulation
- simulation clock
- next-event advancement
- fixed time-step simulation
- event-table method
- event list
- queue system
- multi-server queue
- single-server queue
- FCFS
- arrival process
- service time
- waiting time
- queue length
- server utilization
- warm-up
- replication
- 离散系统
- 离散事件仿真
- 离散事件模拟
- 模拟时钟
- 下次事件推进
- 时间步长法
- 事件表法
- 事件队列
- 排队系统
- 多服务台
- 单服务台
- 先到先服务
- 到达间隔
- 服务时间
- 等待时间
- 队长
- 服务利用率

## Problem Patterns
- A contest problem involves queues, service windows, logistics checkpoints, hospital/port/traffic/service counters, machine repair, call centers, or any system whose state changes at random event times.
- The output is average waiting time, queue length, utilization, throughput, delay probability, congestion, idle time, or service capacity.
- Arrivals, departures, failures, repairs, starts, completions, or dispatch events drive system state.
- The system is not well represented by a continuous ODE because changes happen as jumps at event times.
- A simulation is used to compare staffing, capacity, scheduling, or service-rule policies.
- The problem asks whether one service plan, server count, or assignment rule is better than another.

## Applicability Conditions
- Event types and state variables can be defined.
- Input processes such as interarrival time, service time, routing probability, or batch size can be estimated or assumed with sensitivity.
- A service discipline is specified, such as FCFS, priority, shortest processing time, or appointment rule.
- Server assignment and tie-breaking rules can be stated, especially for multi-server systems.
- A finite horizon, steady-state regime, or stopping condition is clear.
- The model can run enough replications or long enough time to estimate performance metrics stably.

## Contraindications
- Do not use discrete-event simulation when a closed-form queueing formula or deterministic calculation is sufficient for the requested precision.
- Do not simulate event systems with a fixed tiny time step unless events genuinely occur on a regular grid or the approximation is justified.
- Do not claim steady-state averages from a short transient run without warm-up handling.
- Do not model correlated arrivals/services as independent without justification.
- Do not use a queueing simulation to hide missing capacity constraints, scheduling rules, or invalid input distributions.

## Algorithm Core
- Discrete-event route:
  1. define simulation clock `t`, event types, state variables, future-event list, and stopping rule;
  2. initialize state and schedule initial events;
  3. move clock to the earliest future event;
  4. update system state, metric accumulators, and future events;
  5. repeat until horizon, customer count, or precision target is reached;
  6. summarize metrics with uncertainty and diagnostics.
- Single-server FCFS recurrence:
  - generate arrival times `a_i` from interarrival times and service times `s_i`;
  - set `start_i = max(a_i, depart_{i-1})`;
  - set `wait_i = start_i - a_i`;
  - set `depart_i = start_i + s_i`;
  - customer-average wait is `mean(wait_i)`.
- Time-average metrics:
  - average queue length and utilization require accumulating state duration over clock intervals, not only averaging event records.
- Multi-server service route:
  - keep each server's next-free time;
  - if one or more servers are free at arrival time, assign by the stated rule;
  - if all servers are busy, assign to the earliest-free server and set wait as `next_free - arrival`;
  - update that server's next-free time and busy-time accumulator.
- Fixed time-step route:
  - use when arrivals/service opportunities are naturally counted per equal time unit or the approximation is explicitly validated;
  - report the step size and audit sensitivity before comparing policies.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| simulation clock | Tracks simulated time | Must not be confused with loop index |
| next-event advance | Efficiently jumps to next arrival/departure/event | Requires ordered event list or equivalent recurrence |
| fixed-interval advance | Regular time-step approximation | Use only with justified grid or low event-density sensitivity |
| event-table method | Processes irregular arrivals/departures in chronological order | Prefer for queue systems with variable interarrival/service times |
| event list | Stores future events by time and type | Needed for multi-event/multi-server systems |
| state update | Applies event consequences | Must preserve chronological feasibility |
| metric accumulator | Records waits, queue-length time area, busy-time area | Denominator must match customer/time average |
| server next-free vector | Tracks multi-server availability | Required for multi-server assignment and utilization |
| tie-breaking rule | Chooses among multiple free servers | Must be stated to reproduce service allocation |
| hand-traced event table | Debugs the first few arrivals and departures | Cheap validation before long simulation runs |
| replication | Repeats simulation under different seeds | Required for uncertainty when results matter |
| warm-up deletion | Removes transient bias for steady-state metrics | Needed when initial empty state is artificial |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Interarrival distribution | Estimate from arrival data or justify a process assumption | Fit/sanity check and sensitivity |
| Service-time distribution | Fit or justify by service mechanism | Mean/variance/support check |
| Exponential parameter | Confirm whether software uses mean/scale or rate | Empirical mean check; MATLAB `exprnd(mu)` uses mean |
| Number of servers | Treat as a decision/capacity parameter | Utilization and queue stability |
| Assignment rule | State how customers/jobs choose servers and how ties are resolved | First-event trace and server-count balance |
| Queue discipline | State FCFS/priority/rule explicitly | Event trace audit |
| Run horizon/customer count | Match finite-horizon task or steady-state objective | Horizon sensitivity |
| Random seed and replications | Fix seed for reproducibility; vary for robustness | CI or repeated-seed spread |
| Initial state | Empty or loaded system changes early results | Warm-up or initial-condition sensitivity |

## Validation Requirements
- Event contract: event types, event times, state variables, transition rules, and future-event generation.
- Clock-policy contract: choose fixed time-step, next-event, event-table, or hybrid simulation and justify it.
- Input audit: distribution, parameters, data source or assumption, seed, and sample diagnostics.
- Chronology audit: every customer/job satisfies `arrival <= start <= depart`; waits are nonnegative.
- First-events trace: show or test the first 5-10 arrivals/jobs with server assignment, start, departure, wait, and idle time.
- Server accounting: for each server, busy time plus idle time equals the simulated horizon after boundary handling.
- Metric audit: distinguish customer-average and time-average metrics.
- Replication uncertainty: confidence interval, repeated-seed spread, or enough independent runs for final metrics.
- Warm-up/horizon audit when reporting steady-state behavior.
- Baseline comparison: compare to simple queueing formula, deterministic limit, hand-calculated toy example, or extreme-capacity sanity check when possible.
- Policy comparison must use common random numbers or enough replications to avoid random-noise rankings.

## Failure Signs
- The paper says "discrete simulation" but has no event list, clock, or state-transition table.
- The simulation never states whether it uses time-step or event-table advancement.
- Average queue length or utilization is computed from event rows without time weighting.
- A single run's waiting time is used to rank service policies.
- "No waiting occurred" in one finite run is treated as proof that capacity is sufficient.
- Multi-server allocation changes results but the tie-breaking/earliest-free rule is absent.
- Arrival or service distributions are arbitrary and not stress-tested.
- Exponential mean/rate or service-time indexing is wrong.
- Utilization exceeds 1, wait is negative, or departure precedes service completion.
- The system is unstable, but the paper reports a finite short-run average as if capacity is adequate.

## Repair Moves
- Add an event/state/metric contract table before results.
- Add a clock-policy paragraph and switch to event-table simulation when events are irregular.
- Rewrite single-server simulation using `start_i`, `wait_i`, and `depart_i` recurrence.
- Add a hand-traced first 5-10 events table to catch chronology errors.
- For multi-server queues, track a server next-free vector and per-server busy/idle ledgers.
- Add distribution parameterization tests and sample diagnostics.
- Run multiple replications and report mean with interval/spread.
- Add warm-up deletion or state clearly that the result is finite-horizon from an initially empty system.
- Compare against M/M/1 or M/G/1 approximations when assumptions fit, or against deterministic capacity lower/upper bounds.
- Use common random numbers when comparing service policies.

## Paper Usage
- Present discrete-event simulation as "event mechanism + simulation clock + state transition + metric estimation".
- Include a compact event table or flowchart only if it names event types and state updates.
- Report input distributions and parameter sources before performance metrics.
- For queues, show wait-time, queue-length, and utilization definitions with the correct denominator.
- Phrase stochastic outputs as estimated averages under the stated input processes and horizon.

## Source Materials
- Useful sections: discrete-system definition, simulation clock, next-event advance, single-server queue variables, average wait/queue/utilization metrics, arrival/service distribution example.
- Reliability: medium teaching source; promotes basic discrete-event simulation obligations, not advanced queueing-network theory.

## Confidence
- medium: strong for contest-level queue/discrete-event simulation discipline; multi-server networks, priority queues, and simulation optimization need additional specialized cards.
