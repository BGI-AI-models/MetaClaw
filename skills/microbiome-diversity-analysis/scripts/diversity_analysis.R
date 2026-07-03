# Reference: vegan 2.6+, ggplot2 3.5+, base R ≥ 4.5 | Verify API if version differs.
# Alpha and beta diversity analysis using vegan + base R only.
#
# Audit 2026-06-09: this reference used to import phyloseq for its
# `phyloseq()` container, `rarefy_even_depth`, `estimate_richness`,
# `phyloseq::distance`, `ordinate`, `plot_ordination`. phyloseq was dropped
# from openclaw/downstream:1.1.1 because it isn't installable from any
# Chinese Bioc mirror reliably; the same analyses are expressible with
# vegan + base R + ggplot2 (all three already in the image). This rewrite
# uses that stack.
library(vegan)
library(ggplot2)

# Inputs (LLM-customizable in the generated copy):
#   abundance.tsv       — sample × taxon integer count matrix (samples as rows)
#   metadata.tsv        — sample × covariates table, must include `Group`
# When microbiome-profile-merge has run, prefer its `merged_count_table.tsv`
# (already integer counts derived from the MetaPhlAn library size).
otu_mat <- as.matrix(read.delim('abundance.tsv', row.names = 1,
                                 check.names = FALSE, comment.char = '#'))
# vegan convention: samples are rows, taxa are columns. Transpose if the
# table came in with taxa as rows (rows >> cols).
if (nrow(otu_mat) > ncol(otu_mat)) otu_mat <- t(otu_mat)
metadata <- read.delim('metadata.tsv', row.names = 1, check.names = FALSE)
common <- intersect(rownames(otu_mat), rownames(metadata))
if (length(common) < 4) stop('fewer than 4 shared samples between abundance and metadata')
otu_mat  <- otu_mat[common, , drop = FALSE]
metadata <- metadata[common, , drop = FALSE]
cat('Samples:', nrow(otu_mat), '| Taxa:', ncol(otu_mat), '\n')

# ── Input-contract guard ──────────────────────────────────────────────────
# vegan::rrarefy and PERMANOVA-on-counts need integer counts. MetaPhlAn4
# relative abundance (rows ≈ 100 or ≈ 1) would silently misbehave.
if (!all(otu_mat == floor(otu_mat), na.rm = TRUE)) {
    stop('abundance table has non-integer values — looks like relative ',
         'abundance. Use microbiome-profile-merge merged_count_table.tsv.')
}
sample_totals <- rowSums(otu_mat)
if (all(abs(sample_totals - 100) < 5, na.rm = TRUE) ||
    all(abs(sample_totals - 1)   < 0.05, na.rm = TRUE)) {
    stop('sample sums look like relative abundance (≈100 or ≈1 per sample). ',
         'Use microbiome-profile-merge merged_count_table.tsv.')
}

# ── Rarefaction ───────────────────────────────────────────────────────────
min_depth <- min(rowSums(otu_mat))
cat('Minimum sample depth:', min_depth, '\n')
set.seed(42)
rare <- rrarefy(otu_mat, sample = min_depth)

# ── Alpha diversity ───────────────────────────────────────────────────────
# Observed/Chao1 from estimateR (vegan); Shannon/Simpson from diversity().
est   <- estimateR(rare)              # 4 × n matrix: S.obs / S.chao1 / S.ACE / SEs
alpha <- data.frame(
    Observed = est['S.obs',    ],
    Chao1    = est['S.chao1',  ],
    Shannon  = diversity(rare, index = 'shannon'),
    Simpson  = diversity(rare, index = 'simpson')
)
alpha$Group <- metadata[rownames(alpha), 'Group']

cat('\nAlpha diversity by group:\n')
print(aggregate(Shannon ~ Group, data = alpha,
                FUN = function(x) c(mean = mean(x), sd = sd(x))))

kw <- kruskal.test(Shannon ~ Group, data = alpha)
cat('\nKruskal-Wallis test (Shannon):\n')
cat(sprintf('  Chi-squared = %.2f, p = %.4f\n', kw$statistic, kw$p.value))

p_alpha <- ggplot(alpha, aes(x = Group, y = Shannon, fill = Group)) +
    geom_boxplot(alpha = 0.7) +
    geom_jitter(width = 0.2, size = 2, alpha = 0.5) +
    theme_minimal() +
    labs(title = 'Shannon Diversity', y = 'Shannon Index') +
    theme(legend.position = 'none')
ggsave('alpha_diversity.pdf', p_alpha, width = 6, height = 5)

# ── Beta diversity (Bray-Curtis) ──────────────────────────────────────────
bray <- vegdist(rare, method = 'bray')

# PERMANOVA. permutations=999 standard; 9999 for publication, 99 for quick.
perm <- adonis2(bray ~ Group, data = metadata, permutations = 999)
# sqrt.dist=TRUE silences the "some squared distances are negative and
# changed to zero" warning on non-Euclidean Bray-Curtis — that's a known
# PCoA embedding quirk, not a data problem.
bd <- betadisper(bray, metadata$Group, sqrt.dist = TRUE)
cat('\nPERMANOVA results:\n')
print(perm)
cat('\nBetadisper (group dispersion homogeneity):\n')
print(anova(bd))

# ── PCoA ordination (base R cmdscale; no phyloseq) ────────────────────────
pcoa <- cmdscale(bray, k = 2, eig = TRUE)
coords <- data.frame(PC1 = pcoa$points[, 1],
                     PC2 = pcoa$points[, 2],
                     Group = metadata[rownames(pcoa$points), 'Group'])
varexp <- pcoa$eig[1:2] / sum(pcoa$eig[pcoa$eig > 0]) * 100

p_beta <- ggplot(coords, aes(x = PC1, y = PC2, color = Group)) +
    geom_point(size = 3, alpha = 0.8) +
    stat_ellipse(level = 0.95) +
    theme_minimal() +
    labs(title = sprintf('PCoA (Bray-Curtis)\nPERMANOVA R2=%.2f, p=%.3f',
                         perm$R2[1], perm$`Pr(>F)`[1]),
         x = sprintf('PC1 (%.1f%%)', varexp[1]),
         y = sprintf('PC2 (%.1f%%)', varexp[2]))
ggsave('beta_diversity_pcoa.pdf', p_beta, width = 7, height = 6)

cat('\nPlots saved: alpha_diversity.pdf, beta_diversity_pcoa.pdf\n')
