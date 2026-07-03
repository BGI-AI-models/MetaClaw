# Reference: ALDEx2 1.34+, ggplot2 3.5+, base R ≥ 4.5 | Verify API if version differs.
# Differential abundance testing with ALDEx2 (compositional Dirichlet-MC Wilcoxon).
#
# Audit 2026-06-09: this reference previously imported phyloseq for its
# `phyloseq()` container, `filter_taxa`, `otu_table`, `tax_table`,
# `sample_data`, `nsamples`/`ntaxa`. phyloseq was dropped from
# openclaw/downstream:1.1.1 because no Chinese Bioc mirror reliably serves
# it for the pinned R 4.5 / Bioc 3.21 combination. ALDEx2 only needs a
# features × samples count matrix + a group vector; we read the inputs as
# plain TSVs (the format microbiome-profile-merge emits).
library(ALDEx2)
library(ggplot2)

# Inputs (LLM-customizable in the generated copy):
#   abundance.tsv   — samples × taxa integer counts (or taxa × samples;
#                     transposed automatically below). Prefer
#                     microbiome-profile-merge's merged_count_table.tsv.
#   metadata.tsv    — samples × covariates, must include `Group` column;
#                     exactly two groups required.
#   taxonomy.tsv    — optional; taxon → lineage table, joined into results
#                     if present.
abund <- as.matrix(read.delim('abundance.tsv', row.names = 1,
                              check.names = FALSE, comment.char = '#'))
meta  <- read.delim('metadata.tsv', row.names = 1, check.names = FALSE)

# ALDEx2 expects features × samples — orient accordingly.
if (!all(rownames(meta) %in% colnames(abund))) abund <- t(abund)
common <- intersect(colnames(abund), rownames(meta))
if (length(common) < 4) stop('fewer than 4 shared samples between abundance and metadata')
abund <- abund[, common, drop = FALSE]
meta  <- meta[common, , drop = FALSE]

# ── Input-contract guard ──────────────────────────────────────────────────
# ALDEx2 needs non-negative integer counts. Relative abundance would
# silently zero out under the Dirichlet-MC.
if (!all(abund == floor(abund), na.rm = TRUE) || min(abund, na.rm = TRUE) < 0) {
    stop('abundance is not non-negative integers — ALDEx2 needs counts. ',
         'Use microbiome-profile-merge merged_count_table.tsv.')
}
sample_totals <- colSums(abund)
if (all(abs(sample_totals - 100) < 5, na.rm = TRUE) ||
    all(abs(sample_totals - 1)   < 0.05, na.rm = TRUE)) {
    stop('sample sums look like relative abundance (≈100 or ≈1 per sample). ',
         'Use microbiome-profile-merge merged_count_table.tsv.')
}

# ── Filter low-abundance taxa ─────────────────────────────────────────────
# 10% prevalence (taxon must be detected in ≥10% of samples) and mean ≥10
# reads remove spurious rare taxa with unreliable Dirichlet posteriors.
n_samp    <- ncol(abund)
prev      <- rowSums(abund > 0) / n_samp
mean_ab   <- rowMeans(abund)
keep      <- prev >= 0.10 & mean_ab >= 10
abund     <- abund[keep, , drop = FALSE]
cat('Taxa after filtering:', nrow(abund), '\n')

# ── Groups ────────────────────────────────────────────────────────────────
groups <- factor(meta[colnames(abund), 'Group'])
if (nlevels(groups) != 2) {
    stop(sprintf('ALDEx2 expects exactly 2 groups; got %d (%s)',
                 nlevels(groups), paste(levels(groups), collapse = ', ')))
}
cat('Groups:', paste(levels(groups), collapse = ', '), '\n')

# ── Run ALDEx2 ────────────────────────────────────────────────────────────
# mc.samples=128 is standard; 256+ for publication-grade stability.
cat('\nRunning ALDEx2 (this may take a few minutes)...\n')
aldex_out <- aldex(as.data.frame(abund), as.character(groups),
                   mc.samples = 128, test = 'welch',
                   effect = TRUE, include.sample.summary = FALSE,
                   denom = 'all')
aldex_out$taxon       <- rownames(aldex_out)
aldex_out$significant <- aldex_out$we.eBH < 0.05 & abs(aldex_out$effect) > 1

cat('\nResults summary:\n')
cat('  Total taxa tested:', nrow(aldex_out), '\n')
cat('  Significant (q<0.05, |effect|>1):', sum(aldex_out$significant), '\n')
cat('  Enriched in', levels(groups)[1], ':',
    sum(aldex_out$significant & aldex_out$effect > 0), '\n')
cat('  Enriched in', levels(groups)[2], ':',
    sum(aldex_out$significant & aldex_out$effect < 0), '\n')

# Optional taxonomy join
if (file.exists('taxonomy.tsv')) {
    tax <- read.delim('taxonomy.tsv', row.names = 1, check.names = FALSE)
    aldex_out <- merge(aldex_out, tax, by.x = 'taxon', by.y = 'row.names', all.x = TRUE)
}

aldex_out <- aldex_out[order(-abs(aldex_out$effect)), ]
write.csv(aldex_out, 'aldex2_results.csv', row.names = FALSE)

# Volcano-style effect plot
p <- ggplot(aldex_out, aes(x = effect, y = -log10(we.eBH))) +
    geom_point(aes(color = significant), alpha = 0.6, size = 2) +
    geom_hline(yintercept = -log10(0.05), linetype = 'dashed', color = 'grey50') +
    geom_vline(xintercept = c(-1, 1), linetype = 'dashed', color = 'grey50') +
    scale_color_manual(values = c('grey60', 'firebrick'), name = 'Significant') +
    theme_minimal() +
    labs(x = 'Effect Size', y = '-log10(Adjusted P-value)',
         title = 'ALDEx2 Differential Abundance')

ggsave('aldex2_effect_plot.pdf', p, width = 7, height = 6)
cat('\nSaved: aldex2_results.csv, aldex2_effect_plot.pdf\n')
