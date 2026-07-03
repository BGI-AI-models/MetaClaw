# Assumptions and Diagnostics

Use this reference before interpreting inferential results.

## General Principles

1. Always check assumptions before interpreting test results.
2. Use both visual and formal diagnostic methods.
3. Report violations and any remedial actions.
4. Prefer the least complicated corrective step that fits the problem.

## Common Assumptions

### Independence of observations
- Check the study design and data collection process.
- For time series, check autocorrelation and use time-series methods if needed.
- For clustered data, consider mixed-effects models or GEE.

### Normality
- Use Q-Q plots and histograms as primary checks.
- Shapiro-Wilk is useful for small to moderate samples.
- Mild violations may be acceptable with adequate sample size.
- Severe violations may require transformation or non-parametric alternatives.

### Homogeneity of variance
- Use box plots and residual plots.
- Levene's test is preferred over Bartlett's test when data may be non-normal.
- Welch's corrections are often appropriate when variances differ.

## Test-Specific Notes

### T-tests
- Check independence, normality, and equal variances for independent groups.
- Use Welch's t-test when variances are unequal.
- Use Mann-Whitney U or Wilcoxon signed-rank when normality is poor.

### ANOVA
- Check independence, normality in each group, and homogeneity of variance.
- For repeated measures, check sphericity.
- Use Greenhouse-Geisser or Huynh-Feldt corrections when sphericity is violated.

### Linear regression
- Check linearity, independence, homoscedasticity, normality of residuals, and multicollinearity.
- Use residual plots, Q-Q plots, Durbin-Watson, and VIF as needed.

### Logistic regression
- Check independence, linearity of the logit, multicollinearity, and influential observations.
- Confirm adequate event counts for the number of predictors.

## Outlier Detection

- Use box plots, z-scores, or IQR rules.
- Investigate outliers for data entry errors first.
- If outliers are legitimate, consider robust methods or sensitivity analysis.

## Reporting Assumption Checks

Report:
- which assumptions were checked
- which tests or plots were used
- whether the assumptions were met
- what changed if they were not met
