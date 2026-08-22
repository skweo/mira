# Knowledge Card: statistics/mm-sk-queue-simulation

## Tags
- M/M/1
- M/M/s/K
- finite capacity queue
- multi-server queue
- blocking probability
- loss probability
- discrete-event queue simulation
- exponential interarrival time
- exponential service time
- queue length distribution
- 排队论
- 有限容量
- 多服务台
- 损失率

## Problem Patterns
- A service system has Poisson-like arrivals, exponential-like service times, several servers, and limited waiting space.
- The task asks for average waiting time, sojourn time, queue length, utilization, loss probability, blocking rate, or capacity choice.
- Closed-form assumptions are uncertain or a finite-horizon simulation is easier to adapt.
- Staffing/capacity decisions need both analytic queueing baselines and simulation evidence.

## Applicability Conditions
- Arrival and service distributions can be estimated or assumed and tested.
- Server count `s`, waiting capacity `K`, and service discipline are defined.
- The simulation horizon or customer count is long enough for stable estimates.
- Random seeds and replications can be run.

## Contraindications
- Do not use a finite short run as steady-state evidence without warm-up/horizon sensitivity.
- Do not confuse exponential rate with mean/scale. MATLAB `exprnd(mu)` uses mean, not rate.
- Do not ignore lost customers when the system has finite capacity.
- Do not compare staffing plans using different random noise without common random numbers or replications.

## Algorithm Core
- M/M/1 recurrence:
  - generate arrival times `a_i` and service times `s_i`;
  - `start_i = max(a_i, depart_{i-1})`;
  - `wait_i = start_i - a_i`;
  - `depart_i = start_i + s_i`.
- M/M/s/K event simulation:
  1. keep current clock, next arrival, ordered departure list, and system size `L`;
  2. on arrival, accept into service if `L < s`, queue if `s <= L < s+K`, otherwise count loss;
  3. on departure, start service for next waiting customer if any;
  4. accumulate time-weighted queue-length probabilities and customer wait/sojourn metrics.

## Operators / Mechanisms
| Name | Use | Feasibility note |
|---|---|---|
| next-event clock | Processes arrivals/departures chronologically | Avoid fixed-step approximation |
| finite-capacity loss | Counts rejected arrivals | Required for M/M/s/K |
| time-weighted queue distribution | Estimates `P(L=i)` | Use durations, not event counts alone |
| server busy ledger | Computes utilization | Needed for staffing claims |
| replication | Quantifies stochastic uncertainty | Required for final recommendations |
| analytic baseline | M/M/1, Erlang C/B, or stability check | Use when assumptions fit |

## Parameter and Scaling Rules
| Parameter/objective term | Practical rule | Validation |
|---|---|---|
| Arrival rate `lambda` | Mean interarrival time is `1/lambda` | Sample mean and unit audit |
| Service rate `mu` | Mean service time is `1/mu` | Check software parameter convention |
| Server count `s` | Must satisfy stability for infinite-queue approximation | Utilization and sensitivity |
| Waiting capacity `K` | Defines loss/blocking behavior | Report loss probability |
| Horizon/customer count | Large enough for stable tail metrics | Horizon and warm-up sensitivity |
| Queue length probabilities | Compute by time spent in each state | Sum-to-one audit |

## Validation Requirements
- Input parameter table with rate-vs-mean convention.
- Event trace for first several customers.
- Chronology audit: `arrival <= start <= depart`, nonnegative waits.
- Time-weighted queue-length distribution and sum-to-one check.
- Replication or long-run confidence intervals for wait, sojourn, loss, and queue length.
- Analytic comparison for M/M/1/M/M/s when assumptions fit, or deterministic capacity bounds.
- Sensitivity over `s`, `K`, `lambda`, and `mu` for capacity recommendations.

## Failure Signs
- MATLAB `exprnd(lambda)` is used while `lambda` is described as a rate.
- Queue-length probability is computed by counting event records instead of time duration.
- Loss count is omitted for finite-capacity systems.
- Utilization or stability is not reported.
- A capacity recommendation is based on one simulation seed.

## Repair Moves
- Correct rate/mean parameterization and rerun.
- Add time-weighted state probabilities.
- Add loss probability and service-count ledger.
- Run replications and common-random-number policy comparison.
- Add analytic baseline or limit-case check.

## Paper Usage
- Present as "queueing-theory baseline plus discrete-event simulation".
- Report wait, sojourn, queue length, utilization, and loss together; one metric alone is incomplete.
- State whether results are finite-horizon or steady-state estimates.

## Source Materials
- `$PROJECT_ROOT\Math_Model\queueing_theory_cases`
- Files inspected: `M_M_1.m`, `MMSkteam.m`, `test.m`, `README_import.md`.

## Confidence
- medium-high for queue simulation discipline.
- medium for source-code formulas because parameter naming and mean/rate conventions require auditing before reuse.
