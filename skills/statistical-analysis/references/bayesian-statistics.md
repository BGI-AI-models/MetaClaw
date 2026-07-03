# Bayesian Statistics

Use this reference when the user wants Bayesian analysis, Bayesian interpretation, or a comparison with frequentist results.

## Core ideas

- Parameters have posterior distributions.
- Priors encode previous knowledge or weak regularization.
- The posterior combines the prior and the observed data.
- Credible intervals describe uncertainty directly.
- Bayes factors quantify evidence between hypotheses.

## Priors

- Informative priors: use when prior knowledge is strong and defensible.
- Weakly informative priors: default choice for most workflows.
- Very diffuse priors: use cautiously; they are not automatically neutral.

## Common Bayesian analyses

- Bayesian t-test
- Bayesian ANOVA
- Bayesian correlation
- Bayesian linear regression
- Bayesian logistic regression
- Hierarchical models

## Model checking

- Check convergence with R-hat and effective sample size.
- Inspect trace plots.
- Use posterior predictive checks.
- Perform prior sensitivity analysis when priors matter materially.

## Reporting

Report:
- priors used
- posterior estimates
- credible intervals
- Bayes factors when used
- convergence diagnostics
- posterior predictive checks

Keep the interpretation explicit and do not translate Bayesian outputs into frequentist language without care.
