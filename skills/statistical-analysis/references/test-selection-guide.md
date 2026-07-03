# Test Selection Guide

Use this reference when you need to choose the right statistical test for a question.

## Comparing Groups

### Two independent groups
- Continuous, normal: independent samples t-test
- Continuous, non-normal: Mann-Whitney U test
- Binary: chi-square test or Fisher's exact test when expected counts are small
- Ordinal: Mann-Whitney U test

### Two paired groups
- Continuous, normal: paired t-test
- Continuous, non-normal: Wilcoxon signed-rank test
- Binary: McNemar's test
- Ordinal: Wilcoxon signed-rank test

### Three or more independent groups
- Continuous, normal, equal variances: one-way ANOVA
- Continuous, normal, unequal variances: Welch's ANOVA
- Continuous, non-normal: Kruskal-Wallis test
- Binary or categorical: chi-square test
- Ordinal: Kruskal-Wallis test

### Three or more paired groups
- Continuous, normal: repeated measures ANOVA
- Continuous, non-normal: Friedman test
- Binary: Cochran's Q test

### Multiple factors
- Continuous outcome: two-way ANOVA or higher-way ANOVA
- With covariates: ANCOVA
- Mixed within and between factors: mixed ANOVA

## Relationships Between Variables

### Two continuous variables
- Linear and bivariate normal: Pearson correlation
- Monotonic or non-normal: Spearman rank correlation
- Rank-based data: Spearman or Kendall's tau

### Continuous outcome with predictors
- Single continuous predictor: simple linear regression
- Multiple continuous or categorical predictors: multiple linear regression
- Categorical predictors: ANOVA or ANCOVA framework
- Non-linear relationships: polynomial regression or GAM

### Binary outcome
- Single predictor: logistic regression
- Multiple predictors: multiple logistic regression
- Rare events: exact logistic regression or Firth's method

### Count outcome
- Poisson-distributed: Poisson regression
- Overdispersed counts: negative binomial regression
- Zero-inflated: zero-inflated Poisson or negative binomial

### Time-to-event outcome
- Comparing survival curves: log-rank test
- Modeling with covariates: Cox proportional hazards regression
- Parametric survival models: Weibull, exponential, log-normal

## Agreement and Reliability

- Categorical ratings, 2 raters: Cohen's kappa
- Categorical ratings, >2 raters: Fleiss' kappa or Krippendorff's alpha
- Continuous ratings: intraclass correlation coefficient
- Test-retest: ICC or Pearson correlation
- Internal consistency: Cronbach's alpha
- Continuous method agreement: Bland-Altman analysis

## Categorical Data Analysis

- 2x2 table: chi-square test or Fisher's exact test
- Larger than 2x2: chi-square test
- Ordered categories: Cochran-Armitage trend test
- Paired categories: McNemar's test or McNemar-Bowker test

## Bayesian Alternatives

Any of the above tests can be performed using Bayesian methods. They are useful when you want posterior uncertainty, direct probability statements, or evidence for the null hypothesis.

## Key Considerations

- Small samples: consider exact or non-parametric tests
- Large samples: focus on effect sizes, not just p-values
- Multiple comparisons: use Bonferroni, Holm, FDR, or Tukey HSD as appropriate
- Missing data: understand the mechanism before choosing a handling strategy
- Clustered or nested data: use mixed-effects models or GEE
- Time series: use time-series methods
