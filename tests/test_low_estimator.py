from custom_components.zambretti.low_estimator import estimate_low_properties


def test_low_summary_is_italian_and_contains_pressure_line() -> None:
    low = estimate_low_properties(
        wind_from_deg=20,
        pressure_slope_hpa_per_hr=0.4,
        wind_speed_kn=11,
        wind_speed_history_kn=[15.0, 13.0, 11.0],
        wind_dir_delta_deg=12,
        hemisphere="north",
    )

    summary = low.summary

    assert "Pressione: in aumento (+0.40 hPa/h)." in summary
    assert "Vento attuale:" in summary
    assert "Raffiche:" in summary
    assert "Low to" not in summary
    assert "Pressure:" not in summary
    assert "Current wind:" not in summary
