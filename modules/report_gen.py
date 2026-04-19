"""
PDF report generator using reportlab.
3-page report: 
  Page 1: problem statement + 6-factor scoring table
  Page 2: route comparison + weather conditions
  Page 3: assumptions, heuristics, data sources, and limitations
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from typing import List, Dict, Any


FACTORS = [
    ("Base Signal (RSSI)", "35%", "Normalized from tower averageSignal (dBm), attenuated by distance"),
    ("Distance Decay", "40%", "Haversine to nearest tower, inverse-square falloff at 0.5 km scale"),
    ("Network Type", "25%", "5G/NR=100, LTE=80, UMTS=50, GSM=20"),
    ("Weather Attenuation", "Global ×", "Uniform multiplier 0.70–1.0 based on rain/storm conditions"),
    ("Congestion", "Global ×", "Peak-hour multiplier: 0.85× (5–8 pm), 0.90× (8–10 am), 1.0× otherwise"),
    ("Obstacle Density", "Default", "Constant placeholder (5); real OSM building count query deferred to v2"),
]

DATA_SOURCES = [
    ("Road Geometry", "OpenStreetMap via osmnx", "Drivable road graph for Chennai with edge lengths"),
    ("Cell Towers", "OpenCelliD (MCC 404/405)", "4,663 towers filtered to Chennai bounding box (lat 12.8-13.2, lon 80.1-80.35)"),
    ("Live Weather", "OpenWeatherMap API", "Current conditions refreshed every 10 minutes: rain mm/hr, humidity, storm codes"),
    ("AI Explanation", "Groq Llama 3 8B", "2-sentence plain-English route recommendation summary"),
]


def generate_pdf(
    routes: List[Dict[str, Any]],
    weather: Dict[str, Any],
    output_path: str = 'a_unique_route_report.pdf',
) -> str:
    """
    Generate a 3-page PDF report and return the path.
    """
    doc = SimpleDocTemplate(output_path, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('Title', parent=styles['Heading1'], fontSize=18, alignment=TA_CENTER)
    heading_style = ParagraphStyle('Heading', parent=styles['Heading2'], fontSize=13)
    subheading_style = ParagraphStyle('SubHeading', parent=styles['Heading3'], fontSize=11)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, leading=14)
    small_style = ParagraphStyle('Small', parent=styles['Normal'], fontSize=8, leading=11)
    italic_style = ParagraphStyle('Italic', parent=styles['Normal'], fontSize=9, leading=12, fontName='Helvetica-Oblique')

    story = []

    # ── PAGE 1 ──────────────────────────────────────────────────────────
    story.append(Paragraph("A Unique Route", title_style))
    story.append(Paragraph("Cellular Signal-Aware Routing Engine for Chennai", ParagraphStyle('Sub', parent=styles['Normal'], fontSize=11, alignment=TA_CENTER)))
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph("Problem Statement", heading_style))
    story.append(Paragraph(
        "Emergency vehicles and navigation apps in Chennai frequently route through "
        "cellular dead zones, causing service disruption and delayed response times. "
        "A Unique Route scores every road segment using a 6-factor model to produce "
        "routes that prioritise connectivity alongside travel time.",
        body_style,
    ))
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("6-Factor Signal Scoring Model", heading_style))
    factor_data = [["Factor", "Weight", "Source"]] + [[f, w, s] for f, w, s in FACTORS]
    factor_table = Table(factor_data, colWidths=[5.5*cm, 2*cm, 8*cm])
    factor_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0f0f0'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 1), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ('ALIGN', (1, 0), (1, -1), 'CENTER'),
    ]))
    story.append(factor_table)

    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph(
        "Dead Zone Threshold: Score &lt; 30 corresponds to ITU-R P.1546 LTE signal floor of "
        "-100 dBm, below which handoff failure probability exceeds 40%.",
        small_style,
    ))

    story.append(Spacer(1, 0.4*cm))
    story.append(Paragraph("Data Sources", heading_style))
    ds_data = [["Source", "Provider", "Description"]] + [[s, p, d] for s, p, d in DATA_SOURCES]
    ds_table = Table(ds_data, colWidths=[3.5*cm, 4.5*cm, 7.5*cm])
    ds_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#f0f0f0'), colors.white]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]))
    story.append(ds_table)

    story.append(PageBreak())

    # ── PAGE 2 ──────────────────────────────────────────────────────────
    story.append(Paragraph("Route Comparison", heading_style))

    route_data = [["Route", "ETA (min)", "Score", "Dead Zones"]] + [
        [r['name'], str(r['eta_min']), str(r['score']), str(r['dead_zones'])]
        for r in routes
    ]
    route_table = Table(route_data, colWidths=[4*cm, 3*cm, 3*cm, 3*cm])
    route_colors = {'Fastest': '#ffcccc', 'Connected': '#ccccff', 'Blended': '#ccffcc'}
    route_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
    ])
    for i, r in enumerate(routes, start=1):
        bg = colors.HexColor(route_colors.get(r['name'], '#ffffff'))
        route_style.add('BACKGROUND', (0, i), (-1, i), bg)
    route_table.setStyle(route_style)
    story.append(route_table)
    story.append(Spacer(1, 0.4*cm))

    story.append(Paragraph("Weather Conditions at Generation", heading_style))
    weather_text = (
        f"Description: <b>{weather.get('description', 'N/A')}</b> &nbsp; "
        f"Humidity: <b>{weather.get('humidity', 'N/A')}%</b> &nbsp; "
        f"Rain: <b>{weather.get('rain_mm', 0):.1f} mm/hr</b> &nbsp; "
        f"Storm Penalty: <b>{weather.get('storm_penalty', 0)}</b>"
    )
    story.append(Paragraph(weather_text, body_style))

    story.append(PageBreak())

    # ── PAGE 3: Assumptions, Heuristics & Limitations ──────────────────
    story.append(Paragraph("Assumptions, Heuristics &amp; Limitations", title_style))
    story.append(Spacer(1, 0.3*cm))

    # Signal Model Assumptions
    story.append(Paragraph("Signal Model Assumptions", heading_style))

    story.append(Paragraph("Base Signal (RSSI) Normalization", subheading_style))
    story.append(Paragraph(
        "The -110 to -50 dBm range is assumed to represent the practical floor and ceiling of "
        "cellular signal in an urban environment. Real signals can go below -110 in deep "
        "indoor/underground scenarios, which would be clipped to 0.",
        body_style,
    ))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Distance Decay", subheading_style))
    story.append(Paragraph(
        "Inverse-square falloff is borrowed from free-space path loss physics, but real urban signal "
        "does not follow inverse-square &mdash; buildings cause multipath, diffraction, and reflections. "
        "The model assumes open-space propagation geometry, which is a known simplification.",
        body_style,
    ))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Network Type Scoring", subheading_style))
    story.append(Paragraph(
        "The scores (5G=100, LTE=80, UMTS=50, GSM=20) are entirely heuristic. There is no empirical "
        "basis for the exact values &mdash; it is a monotonic ordering that assumes network generation "
        "correlates linearly with usability. A weak 5G signal can be worse than a strong LTE one.",
        body_style,
    ))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Weight Vector", subheading_style))
    story.append(Paragraph(
        "The weight vector [0.30, 0.15, 0.15, 0.20, 0.10, 0.10] is completely expert-set, not learned "
        "from data. A production v2 would learn these weights from driver preference data using "
        "Multi-Criteria Decision Making optimization.",
        body_style,
    ))
    story.append(Spacer(1, 0.3*cm))

    # Weather Assumptions
    story.append(Paragraph("Weather Attenuation Assumptions", heading_style))

    story.append(Paragraph("ITU-R P.838 Application", subheading_style))
    story.append(Paragraph(
        "The rain attenuation formula (rain_rate^0.63 &times; frequency_factor) is a real ITU standard, "
        "but it is designed for point-to-point microwave links &mdash; not mobile cellular at street level. "
        "Applying it to a routing model is a creative first-order approximation, not a validated use of the standard.",
        body_style,
    ))
    story.append(Spacer(1, 0.2*cm))

    story.append(Paragraph("Spatial Uniformity", subheading_style))
    story.append(Paragraph(
        "Weather is assumed to be spatially uniform across all of Chennai during the 10-minute cache window. "
        "In reality, localized rainfall can vary significantly across the city.",
        body_style,
    ))
    story.append(Spacer(1, 0.3*cm))

    # Dead Zone Threshold
    story.append(Paragraph("Dead Zone Threshold", heading_style))
    story.append(Paragraph(
        "Score &lt; 30 is mapped to ITU-R P.1546's -100 dBm LTE signal floor, below which handoff failure "
        "probability exceeds 40%. The mapping from the composite 0&ndash;100 score back to a dBm value is a "
        "narrative justification to make the threshold defensible, not a mathematically derived threshold.",
        body_style,
    ))
    story.append(Spacer(1, 0.3*cm))

    # Routing Assumptions
    story.append(Paragraph("Graph &amp; Routing Assumptions", heading_style))

    assumptions_list = [
        "<b>30 km/h average speed:</b> Every road in Chennai &mdash; arterials, residential lanes, highways &mdash; "
        "gets the same 30 km/h average. Real ETA depends on road class, signal timing, and actual traffic.",

        "<b>Edge midpoint scoring:</b> A single midpoint per road segment is used to query the KDTree. "
        "A long segment crossing a dead zone boundary receives one score for the whole segment, missing the transition.",

        "<b>Obstacle density default = 5:</b> Building count within 100m is the intended input, but OSM building "
        "queries are computationally expensive, so a constant default is assumed.",

        "<b>Congestion model:</b> Rush hour is 5&ndash;8pm at 0.65x multiplier, flat 1.0x otherwise. "
        "No morning rush, no weekend variation, no real-time traffic data. It is a two-state approximation.",
    ]
    for item in assumptions_list:
        story.append(Paragraph("&bull; " + item, body_style))
        story.append(Spacer(1, 0.15*cm))

    story.append(Spacer(1, 0.3*cm))

    # Data Source Assumptions
    story.append(Paragraph("Data Source Assumptions", heading_style))

    data_assumptions = [
        "<b>OpenCelliD staleness:</b> Tower locations are crowd-sourced and may be months or years stale. "
        "Decommissioned or upgraded towers still appear in the dataset.",

        "<b>Nearest tower &ne; serving tower:</b> The model assumes your phone connects to the geometrically "
        "nearest tower. In reality, phones connect to the strongest signal, accounting for beam direction, "
        "load balancing, and handoff logic. Nearest-by-distance is a proxy.",

        "<b>Signal strength synthesis:</b> OpenCelliD RSSI data was zero for all towers in the Chennai dataset. "
        "Synthetic RSSI values were generated per network type (LTE: -75 to -55, GSM: -95 to -70) as a "
        "demonstration substitute for drive-test measurements.",
    ]
    for item in data_assumptions:
        story.append(Paragraph("&bull; " + item, body_style))
        story.append(Spacer(1, 0.15*cm))

    story.append(Spacer(1, 0.4*cm))

    # Honest one-liner
    story.append(Paragraph(
        "<i>\"The weight vector is expert-set rather than learned, the spatial signal model assumes free-space "
        "propagation, and the weather attenuation applies ITU-R P.838 as a first-order approximation outside "
        "its intended use case. A production v2 would calibrate weights from driver feedback data and use "
        "drive-test measurements for ground truth.\"</i>",
        italic_style,
    ))

    doc.build(story)
    return output_path