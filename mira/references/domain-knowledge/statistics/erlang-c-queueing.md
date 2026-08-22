# Knowledge Card: statistics/erlang-c-queueing

## Tags
- Erlang C
- Erlang B
- queueing theory
- M/M/s
- M/M/c
- multi-server queue
- call center staffing
- service level
- target answer time
- average speed of answer
- ASA
- average handling time
- AHT
- traffic intensity
- offered load
- Erlang load
- agent occupancy
- wait probability
- probability of delay
- staffing
- capacity planning
- Poisson arrivals
- exponential service
- abandonment
- shrinkage
- 爱尔朗C
- Erlang C公式
- 排队论
- 多服务台
- 多服务台排队
- 呼叫中心
- 坐席
- 座席
- 话务强度
- 业务强度
- 来电率
- 平均处理时长
- 平均等待时间
- 平均应答速度
- 服务水平
- 目标应答时间
- 等待概率
- 占用率
- 人员需求
- 坐席排班
- 泊松到达
- 指数服务
- 放弃率

## Problem Patterns
- A contest problem asks how many service windows, call-center agents, hotline staff, maintenance crews, counters, or identical servers are needed to meet a service-level target.
- The output is minimum staff/server count, probability of waiting, average waiting time, service level within target time, occupancy, or capacity margin.
- Arrival volume and average service/handling time are known or forecast by time interval.
- A quick analytic baseline is needed before discrete-event simulation or staffing optimization.
- The queue is a pooled multi-server FCFS system and customers wait rather than immediately leave.

## Applicability Conditions
- Arrivals are approximately Poisson within each modeled interval.
- Service/handling times can be approximated by an exponential or average-service-time assumption.
- Servers/agents are homogeneous and pooled.
- Queue discipline is FCFS or close enough for aggregate service-level estimation.
- The interval is near steady state or long enough for a stationary approximation.
- Abandonment, retrials, priorities, finite queue capacity, skill routing, and shift breaks are absent, negligible, or handled separately.
- Occupancy satisfies `rho = u/m < 1`.

## Contraindications
- Do not use Erlang C as final evidence for strong time-varying arrivals without interval slicing, simulation, or a nonstationary correction.
- Do not use it when abandonment is material unless an abandonment model or simulation is added.
- Do not treat multi-skill, priority, appointment, batch-service, or network queues as one homogeneous Erlang C pool without justification.
- Do not use it when `m <= u`; the system is unstable and formulas are not meaningful.
- Do not use example Excel formulas with large factorials without checking numerical stability.
- Do not call Erlang C a particle swarm method because of the source folder.

## Algorithm Core
- Basic Erlang C route:
  1. choose an interval length `H`;
  2. estimate calls/jobs `N`, arrival rate `lambda = N/H`, and average handling/service time `T_s`;
  3. compute offered load `u = lambda T_s = N T_s / H`;
  4. choose integer server count `m` and compute occupancy `rho = u/m`;
  5. require `m > u`;
  6. compute probability of waiting `E_C(m,u)`;
  7. compute average waiting time/ASA and service level within target time `t`;
  8. search integer `m` for the minimum staff meeting service-level and occupancy constraints.
- Wait probability formula:
  - `E_C(m,u) = (u^m / m!) / ((u^m / m!) + (1-rho) * sum_{k=0}^{m-1} u^k/k!)`, where `rho = u/m`.
- Average waiting / ASA:
  - `T_w = E_C(m,u) * T_s / (m * (1-rho))`.
- Service level for target answer time `t`:
  - `SL(t) = 1 - E_C(m,u) * exp(-(m-u)t/T_s)`.
- Staffing inversion:
  - iterate `m = ceil(u)+1, ceil(u)+2, ...` until `SL(t) >= target` and occupancy is below the chosen maximum.

## Operators / Mechanisms

| Name | Use | Feasibility note |
|---|---|---|
| interval slicing | Converts time-varying demand into quasi-stationary periods | Needed for daily/weekly call patterns |
| offered-load calculation | Converts arrivals and service time into Erlangs | Units must match |
| occupancy check | Tests capacity margin | `rho` near 1 makes waits explode |
| wait-probability calculation | Computes delay probability | Use stable recursion/log-sum for large `m` |
| service-level calculation | Converts delay distribution to target-time metric | Needs target answer time |
| integer staff search | Finds minimum feasible `m` | Include occupancy and service constraints |
| shrinkage adjustment | Converts required online agents to scheduled agents | Add breaks, absence, training, after-call work if relevant |
| simulation comparison | Checks formula under realistic complications | Required when assumptions are weak |

## Parameter and Scaling Rules

| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Arrival volume `N` | Count or forecast per interval | Forecast error and peak-period sensitivity |
| Interval length `H` | Use same units as service time | Unit audit |
| Arrival rate `lambda` | `N/H` | Cross-check with raw counts |
| Average service time `T_s` / AHT | Include talk, handling, and after-service work if relevant | Distribution and outlier check |
| Offered load `u` | `lambda T_s` or `N*T_s/H` | Both formulas agree |
| Server count `m` | Integer and greater than `u` | Stability and occupancy audit |
| Occupancy `rho` | `u/m`; keep below a defensible maximum | Sensitivity near capacity |
| Target answer time `t` | From service requirement, e.g. answer within 20s | Report with service level |
| Service-level target | Usually a constraint, not an objective ornament | Minimum `m` search and sensitivity |
| Shrinkage factor | Scheduled staff = online staff / available fraction | Source and sensitivity |

## Validation Requirements
- Input contract: interval length, calls/jobs, arrival rate, AHT/service time, target answer time, service-level target, and server count.
- Assumption audit: Poisson arrivals, independent exponential-like service, homogeneous servers, FCFS pooled queue, no abandonment or handled abandonment.
- Unit audit: all rates and times use consistent units.
- Stability audit: `m > u` and `0 < rho < 1`; report occupancy.
- Formula audit: recompute `E_C`, ASA, and `SL(t)` from the same inputs.
- Numerical audit: avoid factorial overflow and compare with a small hand calculation or trusted implementation.
- Staffing table: show candidate `m`, occupancy, wait probability, ASA, and service level; mark the minimum feasible staff.
- Sensitivity: vary arrival volume, AHT, target answer time, service target, and shrinkage.
- Baseline/validation: compare to observed service levels or a discrete-event simulation if assumptions are imperfect.

## Failure Signs
- Erlang C is used with `m <= u` or occupancy at/above 100%.
- The paper gives only a staff number and omits arrival rate, AHT, occupancy, wait probability, ASA, and service level.
- Unit conversion mixes calls/hour, seconds, and minutes incorrectly.
- Time-varying demand is collapsed into a single daily average.
- Abandonment or finite queue capacity is observed but ignored.
- Heterogeneous agents, priorities, or routing rules are hidden under a single `m`.
- Direct `m!` computation overflows or gives inconsistent results for larger `m`.
- A staffing recommendation has no sensitivity to demand/AHT forecast error.

## Repair Moves
- Add an input-contract table and recompute offered load from raw counts.
- Split the day or process into intervals and apply Erlang C per interval.
- Add occupancy and stability checks before any service-level claim.
- Replace direct factorial with a stable Erlang C implementation.
- Add a staffing sensitivity table and choose the minimum feasible integer `m`.
- Add shrinkage to convert online staffing into scheduled staffing.
- If assumptions fail, use Erlang C only as a baseline and add discrete-event simulation or an abandonment/multi-skill queue model.
- Validate on observed intervals if historical queue metrics exist.

## Paper Usage
- Present Erlang C as "arrival forecast + workload + capacity/stability + service-level calculation".
- Place a compact candidate-staffing table next to the staffing recommendation.
- Phrase outputs as steady-state queueing estimates under stated assumptions.
- Use Erlang C to justify capacity baselines before more complex scheduling or optimization.
- Do not overstate: real operations with abandonment, breaks, and multi-skill routing need additional adjustment or simulation.

## Source Materials
- Useful sections: Erlang C wait-probability formula, arrival-rate calculation, average handling time, offered load, occupancy, ASA, service-level target example.
- Reliability: medium-low practical note; useful for formula workflow and warnings, not a rigorous textbook source.

## Confidence
- medium-low: operationally useful for contest-level call-center/service-capacity baselines, but should be paired with queueing theory, observed validation, or simulation for high-stakes final claims.

