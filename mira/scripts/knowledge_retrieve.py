#!/usr/bin/env python3
"""Retrieve Mira domain knowledge cards for a contest project.

The retriever is intentionally simple and deterministic: it scans compact
markdown cards, scores them against project/query terms, and writes the
obligations that must enter the modeling plan.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
WORKSPACE_ROOT = SKILL_ROOT.parents[2] if len(SKILL_ROOT.parents) > 2 else SKILL_ROOT
DEFAULT_CARD_DIRS = [
    SKILL_ROOT / "references" / "domain-knowledge",
    WORKSPACE_ROOT / "Math_Model" / "extended_knowledge_cards",
]
PROJECT_CARD_DIRS = [
    Path("materials") / "extracted" / "knowledge-cards",
    Path("materials") / "extracted" / "model-cards",
]

SECTION_NAMES = [
    "Tags",
    "Problem Patterns",
    "Applicability Conditions",
    "Contraindications",
    "Algorithm Core",
    "Operators / Mechanisms",
    "Parameter and Scaling Rules",
    "Validation Requirements",
    "Failure Signs",
    "Repair Moves",
    "Paper Usage",
    "Source Materials",
    "Confidence",
]

SYNONYMS = {
    "vrptw": ["vehicle routing", "time window", "routing", "路径", "时间窗", "车辆路径"],
    "vrp": ["vehicle routing", "logistics distribution", "distribution routing", "routing", "车辆路径", "物流配送", "配送路径"],
    "tsptw": ["traveling salesman", "time window", "routing", "路径", "时间窗"],
    "no-wait": ["无等待", "等待", "time window", "strict"],
    "time": ["时间", "time window", "arrival", "departure"],
    "window": ["时间窗", "time window"],
    "routing": ["路径", "路线", "route", "graph", "network", "vehicle routing", "物流配送"],
    "route": ["路径", "路线", "routing", "vehicle routing"],
    "logistics": ["logistics distribution", "distribution routing", "vehicle routing", "配送", "物流配送"],
    "distribution": ["logistics distribution", "delivery routing", "vehicle routing", "配送", "配送路径"],
    "delivery": ["logistics distribution", "distribution routing", "vehicle routing", "配送"],
    "sa": ["simulated annealing", "模拟退火", "heuristic", "local search"],
    "simulated": ["模拟退火", "sa"],
    "annealing": ["模拟退火", "sa"],
    "penalty": ["惩罚", "罚函数", "lateness", "violation"],
    "quadratic": ["二次", "平方", "squared"],
    "cluster": ["聚类", "decomposition", "分解"],
    "clustering": ["聚类", "decomposition", "分解"],
    "heuristic": ["启发式", "local search", "metaheuristic"],
    "local": ["局部搜索", "neighborhood", "邻域"],
    "search": ["搜索", "local search", "neighborhood"],
    "logical": ["logic", "constraint programming", "clp", "cp", "logic constraint"],
    "logic": ["logical", "constraint programming", "clp", "cp", "logic constraint"],
    "clp": ["constraint programming", "logical", "logic constraint"],
    "cp": ["constraint programming", "logical", "logic constraint"],
    "milp": ["mixed integer", "integer programming", "linear programming", "lp"],
    "lp": ["linear programming", "milp"],
    "scheduling": ["schedule", "dispatch", "operation", "inventory"],
    "schedule": ["scheduling", "dispatch", "operation", "inventory"],
    "inventory": ["stock", "storage", "tank", "scheduling"],
    "constraint": ["feasibility", "filter", "logical", "hard constraint"],
    "feasibility": ["constraint", "filter", "audit", "hard constraint"],
    "filter": ["feasibility", "constraint", "screening"],
    "copula": ["dependence", "joint distribution", "marginal distribution", "tail dependence"],
    "monte": ["monte carlo", "simulation", "sampling"],
    "carlo": ["monte carlo", "simulation", "sampling"],
    "var": ["value at risk", "risk quantile", "tail probability", "coverage"],
    "risk": ["var", "value at risk", "tail probability", "quantile"],
    "quantile": ["percentile", "tail probability", "risk"],
    "marginal": ["marginal distribution", "cdf", "inverse cdf"],
    "dependence": ["copula", "correlation", "kendall", "spearman"],
    "tail": ["tail dependence", "extreme", "quantile"],
    "kendall": ["rank correlation", "dependence", "copula"],
    "random": ["sampling", "monte carlo", "stochastic", "simulation"],
    "sampling": ["random", "sample", "monte carlo", "simulation"],
    "sample": ["sampling", "random", "monte carlo", "simulation"],
    "integral": ["numerical integration", "sample mean", "hit-or-miss", "area"],
    "integration": ["integral", "numerical integration", "sample mean"],
    "area": ["hit-or-miss", "random point", "integral"],
    "estimator": ["sample mean", "success ratio", "standard error"],
    "mean": ["sample mean", "expectation", "average"],
    "seed": ["random seed", "reproducibility"],
    "uncertainty": ["standard error", "confidence interval", "convergence"],
    "inverse": ["inverse cdf", "quantile function", "inverse transform"],
    "cdf": ["distribution function", "inverse cdf", "quantile function"],
    "rng": ["pseudo-random", "random seed", "random generator"],
    "normal": ["gaussian", "box-muller", "normal distribution"],
    "exponential": ["rate", "scale", "lambda", "exponential distribution"],
    "binomial": ["trials", "success probability", "bernoulli"],
    "poisson": ["count distribution", "lambda", "arrival"],
    "parameterization": ["parameter convention", "rate", "scale", "variance", "standard deviation"],
    "ode": ["differential equation", "continuous system", "dynamic simulation", "numerical integration"],
    "differential": ["ode", "differential equation", "state equation"],
    "euler": ["euler method", "numerical integration", "time step"],
    "step": ["step size", "time discretization", "refinement"],
    "trajectory": ["state trajectory", "dynamic simulation", "time series"],
    "state": ["state variable", "initial condition", "dynamic system"],
    "dynamic": ["dynamic simulation", "continuous system", "state variable"],
    "discrete": ["discrete event", "event simulation", "queue system"],
    "event": ["discrete event", "event list", "next-event"],
    "queue": ["waiting time", "queue length", "server utilization", "fcfs"],
    "server": ["service time", "utilization", "single server"],
    "arrival": ["interarrival", "arrival process", "queue"],
    "service": ["service time", "server utilization", "queue"],
    "utilization": ["server utilization", "busy time", "queue"],
    "erlang": ["erlang c", "queueing", "service level", "call center"],
    "staffing": ["server count", "agent staffing", "service level", "erlang c"],
    "agent": ["call center", "staffing", "occupancy", "erlang c"],
    "occupancy": ["agent occupancy", "utilization", "offered load", "erlang c"],
    "asa": ["average speed of answer", "average waiting time", "erlang c"],
    "aht": ["average handling time", "service time", "offered load"],
    "offered-load": ["traffic intensity", "erlang load", "queueing"],
    "service-level": ["target answer time", "erlang c", "queueing"],
    "pso": ["particle swarm", "particle swarm optimization", "swarm intelligence", "inertia weight", "velocity clamp", "personal best", "global best", "local best", "lbest", "neighborhood topology", "constriction factor", "online performance", "offline performance", "discrete pso", "adaptive mutation pso", "粒子群", "局部版本", "邻域拓扑", "约束因子", "在线性能", "离线性能"],
    "swarm": ["particle swarm", "pso", "gbest", "pbest", "lbest", "local best", "neighborhood topology", "discrete pso", "粒子群"],
    "particle-swarm": ["pso", "particle swarm optimization", "swarm intelligence", "local best", "neighborhood topology", "constriction factor", "discrete pso", "adaptive mutation pso", "粒子群优化"],
    "discrete-pso": ["discrete pso", "particle swarm", "vehicle routing", "particle encoding", "离散粒子群", "粒子编码"],
    "velocity": ["velocity clamp", "speed bound", "pso", "速度限制", "速度边界"],
    "inertia": ["inertia weight", "pso", "惯性权重"],
    "topology": ["neighborhood topology", "local best", "lbest", "ring topology", "wheel topology", "pso"],
    "lbest": ["local best", "local-neighborhood", "neighborhood topology", "pso"],
    "local-best": ["lbest", "local-neighborhood", "neighborhood topology", "pso"],
    "neighborhood-topology": ["local best", "lbest", "ring topology", "wheel topology", "pso", "邻域拓扑"],
    "constriction": ["constriction factor", "pso", "约束因子"],
    "constriction-factor": ["constriction", "pso", "约束因子"],
    "online": ["online performance", "on-line performance", "pso", "在线性能"],
    "offline": ["offline performance", "off-line performance", "pso", "离线性能"],
    "on-line": ["online", "online performance", "pso"],
    "off-line": ["offline", "offline performance", "pso"],
    "parswarm": ["particle matrix", "pso", "matlab"],
    "optswarm": ["pbest", "gbest", "pso", "matlab"],
    "cognitive": ["cognitive coefficient", "c1", "personal best", "pbest", "学习因子"],
    "social": ["social coefficient", "c2", "global best", "gbest", "学习因子"],
    "pbest": ["personal best", "particle swarm", "个体最优"],
    "gbest": ["global best", "particle swarm", "全局最优"],
    "hyperparameter": ["parameter tuning", "pso", "black-box optimization"],
    "粒子群": ["pso", "particle swarm", "粒子群优化", "离散粒子群", "惯性权重", "速度限制"],
    "粒子群算法": ["pso", "particle swarm optimization", "粒子群优化", "离散粒子群", "局部版本", "约束因子", "在线性能", "离线性能"],
    "离散粒子群": ["discrete pso", "particle swarm", "vehicle routing", "粒子编码"],
    "局部版本": ["local best", "lbest", "local-neighborhood", "neighborhood topology", "pso"],
    "邻域拓扑": ["neighborhood topology", "local best", "ring topology", "wheel topology", "pso"],
    "约束因子": ["constriction factor", "constriction", "pso"],
    "在线性能": ["online performance", "online", "pso"],
    "离线性能": ["offline performance", "offline", "pso"],
    "环形": ["ring topology", "neighborhood topology", "pso"],
    "轮形": ["wheel topology", "neighborhood topology", "pso"],
    "自适应变异": ["adaptive mutation", "mutation", "pso", "premature convergence"],
    "粒子编码": ["particle encoding", "decoder", "vehicle assignment", "route order", "discrete pso"],
    "配送路径": ["distribution routing", "vehicle routing", "vrp", "routing", "pso"],
    "物流配送": ["logistics distribution", "vehicle routing", "vrp", "routing"],
    "车辆路径": ["vehicle routing", "vrp", "routing", "discrete pso"],
    "惯性权重": ["inertia weight", "pso"],
    "速度限制": ["velocity clamp", "pso"],
    "warm-up": ["warmup", "transient", "steady state"],
    "replication": ["repeated seeds", "confidence interval", "simulation"],
    "npv": ["net present value", "cash flow", "discount rate", "investment decision"],
    "investment": ["project evaluation", "cash flow", "npv", "risk decision"],
    "discount": ["discount rate", "npv", "cash flow"],
    "cash": ["cash flow", "npv", "investment"],
    "information": ["information value", "signal", "imperfect information", "threshold policy"],
    "threshold": ["threshold policy", "decision threshold", "information value", "waiting option"],
    "waiting": ["waiting option", "delay", "threshold policy", "real option"],
    "policy": ["policy comparison", "strategy comparison", "common random numbers"],
    "strategy": ["policy comparison", "strategy comparison", "common random numbers"],
    "scenario": ["common random numbers", "policy comparison", "monte carlo"],
    "multiserver": ["multi-server queue", "server assignment", "utilization"],
    "multi-server": ["multi-server queue", "server assignment", "utilization"],
    "event-table": ["event table", "next-event", "queue"],
    "timestep": ["time step", "fixed time-step", "simulation clock"],
    "ca": ["cellular automata", "cellular automaton", "grid simulation", "local rule"],
    "cellular": ["cellular automata", "cellular automaton", "grid simulation", "local rule"],
    "automata": ["cellular automata", "cellular automaton", "grid simulation", "local rule"],
    "automaton": ["cellular automata", "cellular automaton", "grid simulation", "local rule"],
    "lattice": ["grid", "cellular automata", "lattice grid"],
    "grid": ["lattice", "cellular automata", "spatial simulation"],
    "moore": ["moore neighborhood", "8-neighbor", "cellular automata"],
    "neumann": ["von neumann neighborhood", "4-neighbor", "cellular automata"],
    "margolus": ["margolus neighborhood", "2x2 block", "lattice gas"],
    "life": ["game of life", "cellular automata"],
    "percolation": ["渗流", "cluster", "cellular automata"],
    "forest-fire": ["forest fire", "森林火灾", "cellular automata"],
    "lattice-gas": ["lattice gas", "格子气", "margolus"],
    "sandpile": ["sand pile", "砂堆", "cellular automata"],
    "synchronous": ["synchronous update", "double buffer", "cellular automata"],
    "boundary": ["boundary condition", "periodic boundary", "reflecting boundary"],
    "markov": ["markov chain", "state transition", "transition matrix", "stationary distribution"],
    "transition": ["transition matrix", "transition probability", "state transition", "markov chain"],
    "stationary": ["steady state", "stationary distribution", "markov chain"],
    "ergodic": ["regular chain", "stationary distribution", "markov chain"],
    "absorbing": ["absorbing chain", "absorbing state", "fundamental matrix"],
    "absorption": ["absorbing chain", "absorption time", "fundamental matrix"],
    "fundamental": ["fundamental matrix", "absorbing chain", "I-Q"],
    "stochastic-matrix": ["transition matrix", "row stochastic", "markov chain"],
    "ga": ["genetic algorithm", "genetic-algorithm", "chromosome", "selection", "crossover", "mutation", "elitism", "遗传算法"],
    "genetic": ["genetic algorithm", "genetic-algorithm", "chromosome", "selection", "crossover", "mutation", "population"],
    "selection": ["roulette selection", "tournament selection", "genetic algorithm"],
    "crossover": ["one-point crossover", "order crossover", "pmx", "genetic algorithm"],
    "mutation": ["genetic algorithm", "diversity", "repair operator"],
    "elitism": ["best-so-far", "genetic algorithm", "elite retention"],
    "fitness": ["objective transform", "genetic algorithm", "fitness function"],
    "遗传算法": ["genetic algorithm", "chromosome", "selection", "crossover", "mutation"],
    "交叉": ["crossover", "genetic algorithm"],
    "变异": ["mutation", "genetic algorithm"],
    "适应度": ["fitness", "genetic algorithm"],
    "ga-bp": ["genetic algorithm", "bp neural network", "weight initialization", "chromosome"],
    "bp": ["backpropagation", "neural network", "mlp"],
    "neural": ["neural network", "bp", "mlp", "classification"],
    "chromosome": ["encoding", "genetic algorithm", "weights", "thresholds"],
    "membership": ["grade", "evaluation", "classification", "fuzzy"],
    "water": ["water quality", "quality evaluation", "indicator"],
    "quality": ["evaluation", "classification", "indicator", "grade"],
    "ablation": ["baseline", "bp-only", "ga-bp", "comparison"],
    "regression": ["ols", "least squares", "ridge", "lasso", "residual", "vif", "回归", "拟合", "最小二乘"],
    "ols": ["regression", "least squares", "residual", "回归"],
    "ridge": ["regression", "regularization", "multicollinearity", "岭回归"],
    "lasso": ["regression", "regularization", "feature selection", "稀疏"],
    "vif": ["regression", "multicollinearity", "variance inflation"],
    "residual": ["regression", "diagnostics", "error", "残差"],
    "pca": ["principal component", "factor analysis", "dimension reduction", "主成分分析", "降维"],
    "factor": ["factor analysis", "pca", "varimax", "因子分析"],
    "kmo": ["factor analysis", "pca", "bartlett"],
    "bartlett": ["factor analysis", "pca", "kmo"],
    "silhouette": ["clustering", "k-means", "dbscan", "cluster validation", "轮廓系数"],
    "k-means": ["clustering", "kmeans", "cluster", "聚类"],
    "kmeans": ["k-means", "clustering", "cluster", "聚类"],
    "dbscan": ["density clustering", "clustering", "eps", "minpts"],
    "ward": ["hierarchical clustering", "dendrogram", "层次聚类"],
    "sobol": ["sensitivity", "global sensitivity", "variance decomposition", "saltelli", "敏感性"],
    "morris": ["sensitivity", "screening", "elementary effects", "灵敏度"],
    "saltelli": ["sobol", "sensitivity", "sampling"],
    "sensitivity": ["robustness", "perturbation", "sobol", "morris", "灵敏度", "敏感性", "稳健性"],
    "robustness": ["sensitivity", "perturbation", "stability", "稳健性"],
    "game": ["game theory", "nash", "payoff matrix", "evolutionary game", "博弈"],
    "nash": ["game theory", "equilibrium", "payoff matrix", "纳什均衡"],
    "payoff": ["game theory", "nash", "支付矩阵"],
    "evolutionary-game": ["replicator dynamics", "ess", "game theory", "演化博弈"],
    "pareto": ["multiobjective", "nsga-ii", "non-dominated", "front", "帕累托"],
    "multiobjective": ["multi-objective", "pareto", "nsga-ii", "non-dominated", "多目标"],
    "multi-objective": ["multiobjective", "pareto", "nsga-ii", "non-dominated", "多目标"],
    "nsga2": ["nsga-ii", "multiobjective", "pareto", "crowding distance"],
    "nsga-ii": ["nsga2", "multiobjective", "pareto", "non-dominated sorting"],
    "non-dominated": ["pareto", "nsga-ii", "multiobjective", "非支配"],
    "hypervolume": ["pareto", "multiobjective", "hv"],
    "little": ["queueing", "queue", "waiting time", "little law", "排队论"],
    "jackson": ["queueing network", "queueing", "排队网络"],
    "mmc": ["m/m/c", "queueing", "server", "erlang"],
    "m/m/c": ["queueing", "server", "erlang", "waiting time"],
    "simpy": ["discrete event", "queueing", "simulation"],
    "rigid-chain": ["chain kinematics", "rigid segment", "arc length", "fixed joint spacing", "刚性链"],
    "chain": ["rigid-chain", "chain kinematics", "linked segments", "fixed-distance links"],
    "arc-length": ["curve parameterization", "spiral", "chain kinematics"],
    "spiral": ["archimedean spiral", "arc length", "chain kinematics", "螺线"],
    "archimedean": ["spiral", "arc length", "阿基米德螺线"],
    "collision": ["separating axis", "sat", "overlap", "oriented rectangle", "碰撞"],
    "sat": ["separating axis theorem", "collision", "oriented rectangle", "obb", "分离轴"],
    "separating-axis": ["sat", "collision", "oriented rectangle", "分离轴"],
    "obb": ["oriented bounding box", "collision", "sat"],
    "oriented-rectangle": ["obb", "collision", "sat"],
    "extremum": ["maximum", "minimum", "peak", "continuous refinement", "极值"],
    "peak": ["maximum", "extremum", "local refinement", "峰值"],
    "maximum": ["max", "peak", "extremum", "continuous search"],
    "minimum": ["min", "extremum", "continuous search"],
    "grid-search": ["coarse scan", "discrete scan", "continuous refinement", "local search"],
    "coarse-scan": ["grid search", "discrete scan", "integer second", "refinement"],
    "discrete-scan": ["grid search", "coarse scan", "integer second", "continuous refinement"],
    "integer-second": ["coarse scan", "discrete scan", "sub-second", "continuous refinement"],
    "continuous-refinement": ["local refinement", "golden section", "ternary search", "brent"],
    "continuous-search": ["continuous refinement", "extremum", "golden section", "brent"],
    "golden-section": ["continuous refinement", "unimodal search", "extremum"],
    "ternary-search": ["continuous refinement", "unimodal search", "extremum"],
    "brent": ["continuous optimization", "minimize_scalar", "extremum"],
    "minimize_scalar": ["brent", "bounded search", "continuous refinement"],
    "root_scalar": ["threshold crossing", "continuous refinement", "brent"],
    "logistic": ["logistic regression", "logit", "binary classification", "glm", "sigmoid", "逻辑回归"],
    "logit": ["logistic regression", "binary classification", "odds ratio", "逻辑回归"],
    "glm": ["logistic regression", "binomial", "maximum likelihood"],
    "sigmoid": ["logistic regression", "classification", "probability"],
    "roc": ["classification", "auc", "threshold", "logistic regression", "svm"],
    "auc": ["roc", "classification", "threshold"],
    "confusion": ["confusion matrix", "classification", "precision", "recall"],
    "miv": ["mean impact value", "neural network", "feature importance", "variable screening", "平均影响值"],
    "mean-impact": ["miv", "neural network", "feature importance"],
    "feature-importance": ["miv", "permutation importance", "ablation", "variable screening"],
    "svm": ["support vector machine", "kernel", "rbf", "libsvm", "fitcsvm", "支持向量机"],
    "support-vector": ["svm", "margin", "kernel", "support vector machine"],
    "kernel": ["svm", "rbf", "polynomial", "kernel scale"],
    "rbf": ["svm", "kernel", "gamma"],
    "libsvm": ["svm", "support vector machine", "c parameter", "gamma"],
    "fitcsvm": ["svm", "support vector machine", "matlab"],
    "gamma": ["svm", "rbf", "kernel"],
    "nasch": ["nagel schreckenberg", "traffic cellular automata", "random slowdown", "lane changing"],
    "traffic-ca": ["traffic cellular automata", "nasch", "flow density", "lane changing"],
    "traffic-flow": ["traffic cellular automata", "flow density", "congestion", "车流"],
    "lane-changing": ["traffic cellular automata", "keep-right", "safe distance", "换道"],
    "random-slowdown": ["traffic cellular automata", "nasch", "stochastic ca", "随机慢化"],
    "flow-density": ["traffic flow", "fundamental diagram", "density sweep"],
    "m/m/1": ["queueing", "single server", "exponential service", "waiting time"],
    "m/m/s/k": ["finite capacity queue", "multi-server queue", "blocking probability", "loss probability"],
    "finite-capacity": ["queueing", "m/m/s/k", "blocking", "loss probability"],
    "blocking": ["finite capacity queue", "loss probability", "m/m/s/k"],
    "loss-probability": ["blocking", "finite capacity queue", "queueing"],
    "yalmip": ["sdpvar", "optimize", "sdpsettings", "solver status", "matlab optimization"],
    "sdpvar": ["yalmip", "optimization modeling", "decision variable"],
    "binvar": ["yalmip", "binary variable", "milp"],
    "intvar": ["yalmip", "integer variable", "milp"],
    "sdpsettings": ["yalmip", "solver options", "gurobi"],
    "solver-status": ["yalmip", "sol.problem", "solver log", "optimization"],
    "gurobi": ["yalmip", "milp", "qp", "solver"],
    "cplex": ["yalmip", "milp", "solver"],
    "mosek": ["yalmip", "sdp", "socp", "solver"],
}


STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "before",
    "by",
    "can",
    "current",
    "data",
    "do",
    "does",
    "each",
    "for",
    "from",
    "has",
    "have",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "md",
    "mira",
    "must",
    "no",
    "not",
    "of",
    "or",
    "paper",
    "path",
    "phase",
    "project",
    "report",
    "root",
    "that",
    "the",
    "this",
    "to",
    "use",
    "used",
    "when",
    "with",
    "without",
}

DOMAIN_SIGNAL_TERMS = {
    "annealing",
    "arrival",
    "clustering",
    "cooling",
    "decomposition",
    "departure",
    "delivery",
    "discrete-pso",
    "distribution-routing",
    "destroy-repair",
    "heuristic",
    "lateness",
    "lexicographic",
    "logical",
    "logic",
    "clp",
    "cp",
    "milp",
    "lp",
    "logistics",
    "scheduling",
    "schedule",
    "inventory",
    "constraint",
    "feasibility",
    "filter",
    "screening",
    "linear",
    "programming",
    "mixed",
    "integer",
    "local",
    "neighborhood",
    "operator",
    "or-opt",
    "penalty",
    "quadratic",
    "relocate",
    "route",
    "routing",
    "sa",
    "search",
    "simulated",
    "swap",
    "time",
    "time-window",
    "tsptw",
    "vrp",
    "vrptw",
    "vehicle-routing",
    "window",
    "2-opt",
    "ablation",
    "backtest",
    "baseline",
    "bp",
    "carlo",
    "cdf",
    "chromosome",
    "clayton",
    "copula",
    "coverage",
    "dependence",
    "discrete",
    "distribution",
    "dynamic",
    "elitism",
    "empirical",
    "event",
    "euler",
    "exceedance",
    "fitness",
    "frank",
    "ga",
    "genetic",
    "genetic-algorithm",
    "gaussian",
    "ga-bp",
    "gbest",
    "gumbel",
    "hyperparameter",
    "inertia",
    "inverse",
    "inverse-cdf",
    "inverse-transform",
    "kendall",
    "marginal",
    "membership",
    "mlp",
    "monte",
    "mutation",
    "neural",
    "normal",
    "ode",
    "parameterization",
    "percentile",
    "pbest",
    "poisson",
    "pseudo-random",
    "probability",
    "pso",
    "quantile",
    "random",
    "rng",
    "risk",
    "sample",
    "sample-mean",
    "sampling",
    "seed",
    "selection",
    "simulation",
    "spearman",
    "standard-error",
    "swarm",
    "transform",
    "tail",
    "uncertainty",
    "utilization",
    "velocity",
    "velocity-clamp",
    "var",
    "warm-up",
    "water",
    "weight",
    "value-at-risk",
    "area",
    "crossover",
    "estimator",
    "expectation",
    "hit-or-miss",
    "integral",
    "integration",
    "reproducibility",
    "queue",
    "replication",
    "npv",
    "net-present-value",
    "cash-flow",
    "discount",
    "investment",
    "information",
    "threshold",
    "waiting",
    "policy",
    "strategy",
    "scenario",
    "common-random",
    "real-option",
    "multiserver",
    "multi-server",
    "event-table",
    "timestep",
    "ca",
    "cellular",
    "automata",
    "automaton",
    "lattice",
    "grid",
    "moore",
    "neumann",
    "margolus",
    "percolation",
    "forest-fire",
    "lattice-gas",
    "sandpile",
    "synchronous",
    "boundary",
    "local-rule",
    "periodic-boundary",
    "markov",
    "transition-matrix",
    "transition-probability",
    "stationary",
    "ergodic",
    "absorbing",
    "absorption",
    "fundamental-matrix",
    "row-stochastic",
    "erlang",
    "erlang-c",
    "queueing",
    "staffing",
    "agent",
    "occupancy",
    "asa",
    "aht",
    "offered-load",
    "service-level",
    "target-answer-time",
    "server",
    "service",
    "particle-swarm",
    "particle-encoding",
    "premature-convergence",
    "lbest",
    "local-best",
    "neighborhood-topology",
    "topology",
    "constriction",
    "constriction-factor",
    "online",
    "offline",
    "online-performance",
    "offline-performance",
    "parswarm",
    "optswarm",
    "state",
    "step",
    "step-size",
    "trajectory",
    "differential",
    "regression",
    "ols",
    "least-squares",
    "ridge",
    "lasso",
    "vif",
    "residual",
    "diagnostics",
    "regularization",
    "multicollinearity",
    "pca",
    "principal-component",
    "factor",
    "factor-analysis",
    "kmo",
    "bartlett",
    "varimax",
    "dimension-reduction",
    "silhouette",
    "k-means",
    "kmeans",
    "dbscan",
    "ward",
    "dendrogram",
    "sobol",
    "morris",
    "saltelli",
    "sensitivity",
    "robustness",
    "perturbation",
    "tornado",
    "game",
    "game-theory",
    "nash",
    "payoff",
    "payoff-matrix",
    "evolutionary-game",
    "replicator",
    "ess",
    "pareto",
    "multiobjective",
    "multi-objective",
    "nsga2",
    "nsga-ii",
    "non-dominated",
    "crowding-distance",
    "hypervolume",
    "hv",
    "little",
    "jackson",
    "mmc",
    "m/m/c",
    "simpy",
    "rigid-chain",
    "chain-kinematics",
    "rigid-segment",
    "linked-segment",
    "arc-length",
    "spiral",
    "archimedean",
    "collision",
    "sat",
    "separating-axis",
    "obb",
    "oriented-rectangle",
    "overlap",
    "extremum",
    "peak",
    "maximum",
    "minimum",
    "grid-search",
    "coarse-scan",
    "discrete-scan",
    "integer-second",
    "continuous-refinement",
    "continuous-search",
    "golden-section",
    "ternary-search",
    "brent",
    "minimize_scalar",
    "root_scalar",
    "logistic",
    "logistic-regression",
    "logit",
    "glm",
    "binomial",
    "sigmoid",
    "odds-ratio",
    "confusion",
    "confusion-matrix",
    "precision",
    "recall",
    "f1",
    "roc",
    "auc",
    "calibration",
    "miv",
    "mean-impact",
    "mean-impact-value",
    "feature-importance",
    "variable-screening",
    "permutation-importance",
    "svm",
    "support-vector",
    "support-vector-machine",
    "kernel",
    "rbf",
    "libsvm",
    "fitcsvm",
    "gamma",
    "margin",
    "nasch",
    "traffic-ca",
    "traffic-flow",
    "lane-changing",
    "keep-right",
    "random-slowdown",
    "flow-density",
    "fundamental-diagram",
    "m/m/1",
    "m/m/s/k",
    "finite-capacity",
    "blocking",
    "loss-probability",
    "time-weighted",
    "yalmip",
    "sdpvar",
    "binvar",
    "intvar",
    "sdpsettings",
    "solver-status",
    "sol.problem",
    "yalmiperror",
    "gurobi",
    "cplex",
    "mosek",
    "二次",
    "分解",
    "启发式",
    "局部",
    "局部版本",
    "邻域拓扑",
    "约束因子",
    "在线性能",
    "离线性能",
    "环形",
    "轮形",
    "惩罚",
    "搜索",
    "无等待",
    "时间",
    "时间窗",
    "模拟退火",
    "概率模型",
    "蒙特卡洛",
    "随机",
    "随机抽样",
    "随机投点",
    "样本量",
    "估计量",
    "平均值估计",
    "数值积分",
    "收敛检验",
    "误差",
    "误差估计",
    "置信区间",
    "抽样",
    "伪随机数",
    "随机变量",
    "逆变换",
    "反函数",
    "分布函数",
    "均匀分布",
    "正态分布",
    "指数分布",
    "二项分布",
    "泊松分布",
    "统计检验",
    "参数化",
    "连续系统",
    "动态模拟",
    "静态模拟",
    "计算机模拟",
    "数学模拟",
    "微分方程",
    "常微分方程",
    "欧拉法",
    "时间离散化",
    "步长",
    "步距",
    "状态变量",
    "初始条件",
    "轨迹",
    "回归",
    "拟合",
    "最小二乘",
    "岭回归",
    "残差",
    "多重共线性",
    "主成分",
    "主成分分析",
    "因子分析",
    "降维",
    "轮廓系数",
    "层次聚类",
    "灵敏度",
    "敏感性",
    "稳健性",
    "摄动",
    "博弈",
    "纳什",
    "纳什均衡",
    "支付矩阵",
    "演化博弈",
    "多目标",
    "帕累托",
    "非支配",
    "拥挤度",
    "超体积",
    "排队论",
    "排队",
    "服务台",
    "等待时间",
    "刚性链",
    "阿基米德螺线",
    "弧长",
    "碰撞",
    "分离轴",
    "有向矩形",
    "包围盒",
    "极值",
    "峰值",
    "最大值",
    "最小值",
    "网格搜索",
    "网格扫描",
    "离散扫描",
    "整数秒",
    "连续搜索",
    "连续加密",
    "局部加密",
    "三分搜索",
    "黄金分割",
    "逻辑回归",
    "二分类",
    "分类阈值",
    "混淆矩阵",
    "支持向量机",
    "核函数",
    "径向基",
    "变量筛选",
    "平均影响值",
    "特征重要性",
    "交通流",
    "元胞自动机交通流",
    "车流密度",
    "随机慢化",
    "换道",
    "基本图",
    "有限容量",
    "损失率",
    "阻塞概率",
    "求解器状态",
    "优化建模",
    "线性规划",
    "整数规划",
    "二次规划",
    "离散系统",
    "离散事件",
    "离散事件仿真",
    "离散事件模拟",
    "模拟时钟",
    "下次事件推进",
    "事件队列",
    "排队系统",
    "单服务台",
    "先到先服务",
    "到达间隔",
    "服务时间",
    "等待时间",
    "队长",
    "服务利用率",
    "时间步长法",
    "事件表法",
    "多服务台",
    "服务台",
    "忙闲",
    "空闲率",
    "频率表",
    "累计概率",
    "风险决策",
    "风险投资",
    "项目投资",
    "净现值",
    "现金流",
    "折现率",
    "购买情报",
    "信息价值",
    "等待策略",
    "技术改造",
    "阈值策略",
    "策略比较",
    "共同随机数",
    "元胞自动机",
    "细胞自动机",
    "点格自动机",
    "网格仿真",
    "格点",
    "离散空间",
    "局部规则",
    "同步更新",
    "邻域",
    "Moore邻域",
    "Von Neumann邻域",
    "Margolus邻域",
    "边界条件",
    "周期边界",
    "生命游戏",
    "森林火灾",
    "渗流",
    "扩散限制聚集",
    "格子气",
    "砂堆",
    "马尔科夫链",
    "马氏链",
    "马尔可夫链",
    "马尔科夫过程",
    "状态转移",
    "转移概率",
    "转移矩阵",
    "状态概率",
    "初始分布",
    "无后效性",
    "正则链",
    "遍历链",
    "平稳分布",
    "稳态概率",
    "吸收链",
    "吸收状态",
    "基本矩阵",
    "失销概率",
    "等级结构",
    "调入比例",
    "退出比例",
    "爱尔朗C",
    "Erlang C公式",
    "排队论",
    "呼叫中心",
    "坐席",
    "座席",
    "坐席排班",
    "话务强度",
    "业务强度",
    "来电率",
    "平均处理时长",
    "平均等待时间",
    "平均应答速度",
    "服务水平",
    "目标应答时间",
    "等待概率",
    "占用率",
    "人员需求",
    "泊松到达",
    "指数服务",
    "放弃率",
    "遗传算法",
    "神经网络",
    "BP神经网络",
    "水质评价",
    "评价模型",
    "分类",
    "隶属度",
    "权值",
    "阈值",
    "权值阈值",
    "染色体",
    "染色体编码",
    "归一化",
    "消融对照",
    "交叉验证",
    "罚函数",
    "聚类",
    "路径",
    "邻域",
}


@dataclass
class CardHit:
    path: str
    title: str
    score: int
    matched_terms: list[str]
    sections: dict[str, str]


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    query_text = build_query(root, args.query, args.from_files)
    card_dirs = collect_card_dirs(root, args.card_dir, args.include_model_knowledge)
    cards = list(scan_cards(card_dirs))
    hits = score_cards(cards, query_text, args.limit, args.min_score, explicit_query=args.query)

    report_path = resolve_path(root, args.write_report) if args.write_report else None
    json_path = resolve_path(root, args.write_json) if args.write_json else None
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown(root, query_text, hits), encoding="utf-8")
    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(
            json.dumps(
                {
                    "generated_at": now(),
                    "root": str(root),
                    "query": query_text,
                    "hits": [asdict(hit) for hit in hits],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    print(f"scanned_cards: {len(cards)}")
    print(f"hits: {len(hits)}")
    for hit in hits:
        print(f"{hit.score:>3} {hit.path} :: {', '.join(hit.matched_terms[:12])}")
    if report_path:
        print(f"wrote: {report_path}")
    if json_path:
        print(f"wrote: {json_path}")
    return 0 if hits else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--query", default="", help="Problem/method terms to retrieve against")
    parser.add_argument("--from-files", nargs="*", default=None, help="Extra project files to include in the query")
    parser.add_argument("--card-dir", action="append", default=[], help="Additional directory containing markdown knowledge cards")
    parser.add_argument("--include-model-knowledge", action="store_true", help="Also scan broad model-card notes; default is domain knowledge cards only")
    parser.add_argument("--limit", type=int, default=5, help="Maximum cards to include")
    parser.add_argument("--min-score", type=int, default=8, help="Minimum score required for a card hit")
    parser.add_argument("--write-report", help="Markdown report path, relative to root when not absolute")
    parser.add_argument("--write-json", help="JSON report path, relative to root when not absolute")
    return parser.parse_args()


def build_query(root: Path, query: str, from_files: list[str] | None) -> str:
    parts = [query]
    rels = from_files or [
        "planning/problem_analysis.md",
        "planning/modeling_plan.md",
        "checks/semantic_audit_report.md",
        "checks/quality_balance_report.md",
        "revisions/iteration_report.md",
    ]
    for rel in rels:
        path = resolve_path(root, rel)
        if path.exists() and path.is_file():
            parts.append(read_text(path)[:20000])
    return "\n".join(part for part in parts if part).strip()


def collect_card_dirs(root: Path, extras: list[str], include_model_knowledge: bool) -> list[Path]:
    dirs: list[Path] = []
    dirs.extend(root / rel for rel in PROJECT_CARD_DIRS)
    dirs.extend(DEFAULT_CARD_DIRS)
    if include_model_knowledge:
        dirs.append(SKILL_ROOT / "references" / "model-knowledge")
    dirs.extend(resolve_path(root, item) for item in extras)
    out: list[Path] = []
    seen: set[str] = set()
    for directory in dirs:
        key = str(directory.resolve()) if directory.exists() else str(directory)
        if key in seen:
            continue
        seen.add(key)
        out.append(directory)
    return out


def scan_cards(card_dirs: Iterable[Path]) -> Iterable[tuple[Path, str]]:
    for directory in card_dirs:
        if not directory.exists():
            continue
        if directory.is_file() and directory.suffix.lower() in {".md", ".markdown"}:
            yield directory, read_text(directory)
            continue
        for path in sorted(directory.rglob("*.md")):
            if path.name.lower() in {"readme.md"}:
                continue
            text = read_text(path)
            if is_card(text, path):
                yield path, text


def is_card(text: str, path: Path) -> bool:
    lower = text.lower()
    if "knowledge card:" in lower or "model card:" in lower:
        return True
    domain_path = "domain-knowledge" in str(path).replace("\\", "/").lower()
    return domain_path and ("## problem patterns" in lower or "## validation requirements" in lower)


def score_cards(
    cards: Iterable[tuple[Path, str]],
    query_text: str,
    limit: int,
    min_score: int,
    explicit_query: str = "",
) -> list[CardHit]:
    query_terms = extract_terms(query_text)
    expanded_terms = expand_terms(query_terms)
    explicit_terms = expand_terms(extract_terms(explicit_query))
    hits: list[CardHit] = []
    for path, text in cards:
        card_terms = extract_terms(text)
        matched = sorted(expanded_terms & card_terms)
        score = len(matched)
        title = extract_title(text, path)
        path_terms = extract_terms(str(path))
        path_matches = sorted(expanded_terms & path_terms)
        if path_matches:
            score += len(path_matches) * 2
            matched = sorted(set(matched) | set(path_matches))
        heading_matches = sorted(expanded_terms & extract_terms(title))
        if heading_matches:
            score += len(heading_matches) * 3
            matched = sorted(set(matched) | set(heading_matches))
        explicit_matches = sorted(explicit_terms & (card_terms | path_terms | extract_terms(title)))
        if explicit_matches:
            score += len(explicit_matches) * 6
            matched = sorted(set(matched) | set(explicit_matches))
        strong_matches = sorted(set(matched) & DOMAIN_SIGNAL_TERMS)
        if strong_matches:
            score += len(strong_matches) * 4
        sections = extract_sections(text)
        if sections:
            score += 2
        if not strong_matches and "domain-knowledge" not in str(path).replace("\\", "/").lower():
            continue
        if score < min_score:
            continue
        hits.append(
            CardHit(
                path=str(path),
                title=title,
                score=score,
                matched_terms=strong_matches or matched,
                sections=sections,
            )
        )
    hits.sort(key=lambda hit: (-hit.score, hit.path.lower()))
    return hits[: max(limit, 1)]


def extract_terms(text: str) -> set[str]:
    lowered = text.lower()
    ascii_terms = re.findall(r"[a-z0-9][a-z0-9+\-_/]{1,}", lowered)
    chinese_terms = re.findall(r"[\u4e00-\u9fff]{2,}", lowered)
    terms = set(ascii_terms)
    for phrase in chinese_terms:
        terms.add(phrase)
        for size in (2, 3, 4):
            if len(phrase) >= size:
                terms.update(phrase[i : i + size] for i in range(0, len(phrase) - size + 1))
    return {term.strip("-_/") for term in terms if is_signal_term(term.strip("-_/"))}


def is_signal_term(term: str) -> bool:
    if not term or term in STOPWORDS:
        return False
    if term.isdigit() and len(term) < 2:
        return False
    if re.fullmatch(r"\d+", term) and int(term) > 80:
        return False
    return len(term) >= 2


def expand_terms(terms: set[str]) -> set[str]:
    out = set(terms)
    for term in list(terms):
        if term in SYNONYMS:
            out.update(item.lower() for item in SYNONYMS[term])
    return out


def extract_title(text: str, path: Path) -> str:
    for line in text.splitlines():
        if line.startswith("# "):
            return line.lstrip("#").strip()
    return path.stem


def extract_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            current = heading.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].append(line)
    compact: dict[str, str] = {}
    for name in SECTION_NAMES:
        body = "\n".join(sections.get(name, [])).strip()
        if body:
            compact[name] = trim_section(body)
    return compact


def trim_section(text: str, max_lines: int = 18) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    if len(lines) <= max_lines:
        return "\n".join(lines).strip()
    return "\n".join(lines[:max_lines] + ["..."]).strip()


def render_markdown(root: Path, query_text: str, hits: list[CardHit]) -> str:
    lines = [
        "# Mira Knowledge Injection",
        "",
        f"- Generated: {now()}",
        f"- Project root: `{root}`",
        f"- Hits: {len(hits)}",
        "",
        "## Query Signals",
        "",
        summarize_query(query_text),
        "",
    ]
    if not hits:
        lines.extend(
            [
                "## Retrieved Cards",
                "",
                "No relevant knowledge card was found. Create a candidate card under `materials/extracted/knowledge-cards/` after reading the source material.",
                "",
            ]
        )
        return "\n".join(lines)

    lines.extend(
        [
            "## Modeling Obligations",
            "",
            "| Card | Matched signals | Must enter modeling plan |",
            "|---|---|---|",
        ]
    )
    for hit in hits:
        obligations = obligation_summary(hit)
        rel = rel_to(root, Path(hit.path))
        lines.append(f"| `{rel}` | {escape_table(', '.join(hit.matched_terms[:12]))} | {escape_table(obligations)} |")

    lines.extend(["", "## Retrieved Cards", ""])
    for hit in hits:
        rel = rel_to(root, Path(hit.path))
        lines.extend(
            [
                f"### {hit.title}",
                "",
                f"- Path: `{rel}`",
                f"- Score: {hit.score}",
                f"- Matched terms: {', '.join(hit.matched_terms[:20])}",
                "",
            ]
        )
        for name in [
            "Problem Patterns",
            "Applicability Conditions",
            "Contraindications",
            "Operators / Mechanisms",
            "Parameter and Scaling Rules",
            "Validation Requirements",
            "Failure Signs",
            "Repair Moves",
            "Paper Usage",
            "Confidence",
        ]:
            body = hit.sections.get(name)
            if body:
                lines.extend([f"#### {name}", "", body, ""])

    lines.extend(
        [
            "## Required Integration",
            "",
            "- Add a `Domain knowledge used` table to `planning/modeling_plan.md`.",
            "- If a card is rejected, record the contraindication or missing applicability condition.",
            "- Carry card validation requirements into code outputs and result analysis.",
            "- If a failure sign appears, run or waive the listed repair moves before final delivery.",
            "",
        ]
    )
    return "\n".join(lines)


def obligation_summary(hit: CardHit) -> str:
    parts: list[str] = []
    if hit.sections.get("Operators / Mechanisms"):
        parts.append("state concrete operators/mechanisms")
    if hit.sections.get("Parameter and Scaling Rules"):
        parts.append("justify parameters/scaling")
    if hit.sections.get("Validation Requirements"):
        parts.append("run named validation")
    if hit.sections.get("Failure Signs"):
        parts.append("watch failure signs")
    if hit.sections.get("Repair Moves"):
        parts.append("define repair route")
    if hit.sections.get("Paper Usage"):
        parts.append("limit paper claims")
    return "; ".join(parts) or "summarize applicable card obligations"


def summarize_query(text: str, limit: int = 700) -> str:
    one_line = re.sub(r"\s+", " ", text).strip()
    if len(one_line) <= limit:
        return one_line or "No explicit query; project artifacts were scanned."
    return one_line[:limit].rstrip() + "..."


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return root / path


def rel_to(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        try:
            return str(path.resolve().relative_to(SKILL_ROOT)).replace("\\", "/")
        except ValueError:
            return str(path)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def escape_table(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", "<br>")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


if __name__ == "__main__":
    raise SystemExit(main())
