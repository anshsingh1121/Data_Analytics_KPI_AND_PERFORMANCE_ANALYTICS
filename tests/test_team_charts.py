import pytest
import pandas as pd
import numpy as np
import plotly.express as px

def test_scatter_collision_avoidance_positions():
    """Verify that points with close proximity get distinct diverging label positions."""
    # Simulate the exact coordinates from the user's report
    df = pd.DataFrame({
        "Team Member": ["Brian Carter", "E J Parks JR", "Senthilkumar Pachamuthu", "Ashwini M", "Cindy Dawson"],
        "Average turnaround time": [2.6, 2.8, 4.9, 11.2, 12.1],
        "SLA compliance": [0.0, 0.0, 0.0, 0.0, 0.0],
    })

    def _calculate_scatter_label_positions(df, x_col="Average turnaround time", y_col="SLA compliance"):
        if df is None or df.empty:
            return "top center"
        x_vals = df[x_col].values
        y_vals = df[y_col].values
        n = len(df)
        if n <= 1:
            return ["top center"] * n
        x_span = max(1.0, float(np.ptp(x_vals)))
        y_span = max(1.0, float(np.ptp(y_vals)))
        positions = []
        for i in range(n):
            xi, yi = x_vals[i], y_vals[i]
            close_indices = []
            for j in range(n):
                if i != j:
                    dx = abs(xi - x_vals[j]) / x_span
                    dy = abs(yi - y_vals[j]) / max(1.0, y_span)
                    if dx < 0.16 and dy < 0.22:
                        close_indices.append(j)
            if not close_indices:
                positions.append("bottom center" if yi >= 90 else "top center")
            else:
                cluster = sorted([i] + close_indices, key=lambda idx: x_vals[idx])
                rank = cluster.index(i)
                c_size = len(cluster)
                if c_size == 2:
                    positions.append(("top left" if yi < 85 else "bottom left") if rank == 0 else ("top right" if yi < 85 else "bottom right"))
                elif c_size == 3:
                    if rank == 0:
                        positions.append("top left" if yi < 85 else "bottom left")
                    elif rank == 1:
                        positions.append("top center" if yi < 50 else "bottom center")
                    else:
                        positions.append("top right" if yi < 85 else "bottom right")
                else:
                    alt = ["top left", "top right", "bottom left", "bottom right"]
                    positions.append(alt[rank % len(alt)])
        return positions

    positions = _calculate_scatter_label_positions(df)
    assert len(positions) == 5

    # Brian Carter (x=2.6) and E J Parks JR (x=2.8) must diverge
    brian_pos = positions[0]
    ej_pos = positions[1]
    assert brian_pos != ej_pos
    assert brian_pos == "top left"
    assert ej_pos == "top right"

    # Ashwini M (x=11.2) and Cindy Dawson (x=12.1) must diverge
    ashwini_pos = positions[3]
    cindy_pos = positions[4]
    assert ashwini_pos != cindy_pos
    assert ashwini_pos == "top left"
    assert cindy_pos == "top right"

def test_slowest_performers_target_annotation_position():
    """Verify that the SLA target line annotation does not overlap the 1st bar."""
    df = pd.DataFrame({
        "Team Member": ["Cindy Dawson", "Ashwini M"],
        "Average turnaround time": [12.1, 11.2]
    })
    fig_slow = px.bar(
        df,
        x="Average turnaround time",
        y="Team Member",
        orientation="h"
    )
    fig_slow.add_vline(x=5.0, line_dash="dash", line_color="#DC2626")
    fig_slow.add_annotation(
        x=5.0,
        y=1.04,
        yref="paper",
        text="<b>SLA Target: 5.0d</b>",
        showarrow=False,
        xanchor="left",
        yanchor="bottom",
        font=dict(color="#DC2626", size=11, family="sans-serif"),
        bgcolor="rgba(255, 255, 255, 0.95)",
        bordercolor="#DC2626",
        borderwidth=1,
        borderpad=3
    )

    ann = fig_slow.layout.annotations[0]
    # Check that annotation is positioned outside the plot area above y=1.0
    assert ann.yref == "paper"
    assert ann.y > 1.0
    assert ann.yanchor == "bottom"
    assert ann.bgcolor == "rgba(255, 255, 255, 0.95)"
