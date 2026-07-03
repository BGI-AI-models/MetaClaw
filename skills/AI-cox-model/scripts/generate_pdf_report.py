#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate PDF summary report for Cox survival analysis."""

import os
from datetime import datetime
from typing import Any, Dict, Optional
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Image,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
)
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


def create_pdf_report(
    result_dir: str,
    config: Dict[str, Any],
    results: Dict[str, Any],
    output_filename: str = "survival_analysis_report.pdf",
) -> str:
    """
    Generate a comprehensive PDF report for Cox survival analysis results.

    Parameters
    ----------
    result_dir : str
        Directory containing analysis results
    config : dict
        Configuration dictionary
    results : dict
        Results dictionary from pipeline
    output_filename : str
        Output PDF filename

    Returns
    -------
    pdf_path : str
        Path to generated PDF
    """
    pdf_path = os.path.join(result_dir, output_filename)

    # Create document
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    # Container for PDF elements
    story = []

    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "CustomTitle",
        parent=styles["Heading1"],
        fontSize=24,
        textColor=colors.HexColor("#003d5c"),
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        "CustomHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=colors.HexColor("#003d5c"),
        spaceAfter=6,
        spaceBefore=12,
        borderColor=colors.HexColor("#cccccc"),
        borderWidth=1,
        borderPadding=6,
    )
    body_style = styles["BodyText"]

    # Title
    story.append(Paragraph("Cox Proportional Hazards Survival Analysis", title_style))
    story.append(
        Paragraph(f"<i>Generated {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>", styles["Normal"])
    )
    story.append(Spacer(1, 0.2 * inch))

    # Executive Summary
    story.append(Paragraph("Executive Summary", heading_style))
    data_path = config.get("data_path", "Unknown")
    mode = config.get("mode", "Unknown")
    n_samples = len(results.get("final_df", []))
    n_features = len(results.get("selected_vars", []))
    c_index = results.get("c_index", 0)

    summary_text = (
        f"<b>Analysis Type:</b> {'Longitudinal survival data' if mode == 'longitudinal' else 'Single-row survival data'}<br/>"
        f"<b>Sample Size:</b> {n_samples} subjects<br/>"
        f"<b>Selected Predictors:</b> {n_features} variables (LASSO selection)<br/>"
        f"<b>Model Performance (C-index):</b> {c_index:.4f}<br/>"
        f"<b>Risk Groups:</b> {config.get('risk_n_groups', 3)} groups ({', '.join(map(str, config.get('risk_group_labels', [])))}) "
    )
    story.append(Paragraph(summary_text, body_style))
    story.append(Spacer(1, 0.15 * inch))

    # Key Findings
    story.append(Paragraph("Key Findings", heading_style))

    findings = _generate_findings(results, config)
    for i, finding in enumerate(findings, 1):
        story.append(Paragraph(f"{i}. {finding}", body_style))

    story.append(Spacer(1, 0.2 * inch))

    # Kaplan-Meier Plot
    story.append(Paragraph("Kaplan-Meier Risk-Stratified Survival Curves", heading_style))
    km_path = os.path.join(result_dir, "km_risk_stratified.png")
    if os.path.exists(km_path):
        story.append(
            Paragraph(
                "<i>Survival curves stratified by risk groups. Separation between curves indicates good model discrimination.</i>",
                styles["Normal"],
            )
        )
        try:
            img = Image(km_path, width=5.5 * inch, height=4.1 * inch)
            story.append(img)
        except Exception as e:
            story.append(Paragraph(f"<i>[Plot could not be embedded: {e}]</i>", styles["Normal"]))
    story.append(Spacer(1, 0.15 * inch))

    # Forest Plot
    story.append(Paragraph("Forest Plot of Selected Variables", heading_style))
    forest_path = os.path.join(result_dir, "forest_plot.png")
    if os.path.exists(forest_path):
        story.append(
            Paragraph(
                "<i>Hazard ratios (HR) with 95% confidence intervals for selected predictors. "
                "The vertical dashed line at HR=1 indicates no effect.</i>",
                styles["Normal"],
            )
        )
        try:
            img = Image(forest_path, width=5.5 * inch, height=3.5 * inch)
            story.append(img)
        except Exception as e:
            story.append(Paragraph(f"<i>[Plot could not be embedded: {e}]</i>", styles["Normal"]))

    story.append(PageBreak())

    # Selected Variables Table
    story.append(Paragraph("Selected Variables (LASSO-Cox)", heading_style))
    selected_vars = results.get("selected_vars")
    if selected_vars is not None and len(selected_vars) > 0:
        var_data = [
            ["Variable", "Coefficient", "HR", "95% CI Lower", "95% CI Upper", "p-value"]
        ]
        for idx, row in selected_vars.iterrows():
            var_data.append([
                str(idx),
                f"{row.get('coef', 0):.4f}",
                f"{row.get('HR', 0):.4f}",
                f"{row.get('CI_lower', 0):.4f}",
                f"{row.get('CI_upper', 0):.4f}",
                f"{row.get('p', 0):.6f}" if "p" in row else "—",
            ])

        var_table = Table(var_data, colWidths=[1.5 * inch, 1 * inch, 0.8 * inch, 1 * inch, 1 * inch, 1 * inch])
        var_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003d5c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), TA_CENTER),
                ("ALIGN", (0, 0), (0, -1), TA_LEFT),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 9),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
                ("FONTSIZE", (0, 1), (-1, -1), 8),
            ])
        )
        story.append(var_table)
    else:
        story.append(Paragraph("<i>No variables selected by LASSO.</i>", styles["Normal"]))

    story.append(Spacer(1, 0.15 * inch))

    # Risk Group Summary
    story.append(Paragraph("Risk Group Summary", heading_style))
    final_df = results.get("final_df")
    if final_df is not None and "risk_group" in final_df.columns:
        risk_stats = final_df.groupby("risk_group", observed=True)[config.get("event_col", "event")].agg(
            ["count", "sum", "mean"]
        )
        risk_stats.columns = ["N Subjects", "N Events", "Event Rate"]
        risk_stats["Event Rate"] = (risk_stats["Event Rate"] * 100).round(2).astype(str) + "%"

        risk_data = [["Risk Group", "N Subjects", "N Events", "Event Rate"]]
        for group, row in risk_stats.iterrows():
            risk_data.append([
                str(group),
                str(int(row["N Subjects"])),
                str(int(row["N Events"])),
                str(row["Event Rate"]),
            ])

        risk_table = Table(risk_data, colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch, 1.5 * inch])
        risk_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#003d5c")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("ALIGN", (0, 0), (-1, -1), TA_CENTER),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
                ("BACKGROUND", (0, 1), (-1, -1), colors.lightblue),
                ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ])
        )
        story.append(risk_table)

    story.append(Spacer(1, 0.2 * inch))

    # Interpretation Guide
    story.append(PageBreak())
    story.append(Paragraph("How to Interpret This Report", heading_style))

    interpretation = [
        ("<b>Hazard Ratio (HR):</b> Measures the relative risk associated with a variable. "
         "HR=1 means no effect, HR>1 increases risk, HR<1 decreases risk. "
         "For example, HR=2 means the variable is associated with 2× the hazard (risk) of the event."),

        ("<b>95% Confidence Interval (CI):</b> Range where we're 95% confident the true HR lies. "
         "If the CI includes 1, the effect is not statistically significant at p<0.05."),

        ("<b>C-Index:</b> Measures how well the model discriminates between subjects who do and don't have the event. "
         "0.5 = random chance, 0.7–0.8 = good, >0.8 = excellent."),

        ("<b>Kaplan-Meier Curves:</b> Show survival probability over time for each risk group. "
         "Steeper decline = higher event rate. Curves that don't separate well indicate weak discrimination."),

        ("<b>Log-Rank Test:</b> Statistical test comparing survival between risk groups. "
         "p<0.05 indicates a significant difference."),

        ("<b>LASSO Selection:</b> Automatically selects variables with non-zero coefficients to prevent overfitting. "
         "Variables with |coef|>threshold are included in the final model."),
    ]

    for text in interpretation:
        story.append(Paragraph(text, body_style))
        story.append(Spacer(1, 0.1 * inch))

    # Build PDF
    doc.build(story)
    return pdf_path


def _generate_findings(results: Dict[str, Any], config: Dict[str, Any]) -> list:
    """Generate key findings text."""
    findings = []

    # C-index finding
    c_index = results.get("c_index", 0)
    if c_index >= 0.8:
        findings.append(
            f"Model shows excellent discrimination (C-index = {c_index:.4f}), "
            "indicating strong ability to differentiate risk groups."
        )
    elif c_index >= 0.7:
        findings.append(
            f"Model shows good discrimination (C-index = {c_index:.4f}), "
            "with reasonable ability to stratify patients by risk."
        )
    else:
        findings.append(
            f"Model discrimination is modest (C-index = {c_index:.4f}). "
            "Consider including additional clinical variables or exploring interaction terms."
        )

    # Variable selection finding
    selected_vars = results.get("selected_vars")
    if selected_vars is not None:
        n_vars = len(selected_vars)
        findings.append(
            f"LASSO regression identified {n_vars} significant predictor(s) "
            f"from the input features."
        )

    # Risk stratification finding
    final_df = results.get("final_df")
    if final_df is not None and "risk_group" in final_df.columns:
        event_col = config.get("event_col", "event")
        risk_groups = final_df["risk_group"].dropna().unique()
        findings.append(
            f"Patients were stratified into {len(risk_groups)} risk groups "
            f"with distinct event rates across groups."
        )

    # PH assumption finding
    if config.get("check_ph_assumptions"):
        findings.append(
            "Proportional hazards assumption was tested. "
            "Review ph_test_results.tsv for detailed results."
        )

    return findings
