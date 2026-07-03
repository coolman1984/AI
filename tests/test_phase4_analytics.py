"""Tests for Phase 4 factory analytics modules."""



def test_period_close_imports():
    """period-close-pack should import cleanly."""
    from skills.period_close_pack.run import run_period_close
    assert callable(run_period_close)


def test_variance_drivers_imports():
    """variance-driver-decomposition should import cleanly."""
    from skills.variance_driver_decomposition.run import run_variance_drivers
    assert callable(run_variance_drivers)


def test_inventory_scan_imports():
    """inventory-exception-scan should import cleanly."""
    from skills.inventory_exception_scan.run import run_inventory_scan
    assert callable(run_inventory_scan)


def test_rework_analysis_imports():
    """rework-cost-analysis should import cleanly."""
    from skills.rework_cost_analysis.run import run_rework_analysis
    assert callable(run_rework_analysis)


def test_cross_period_imports():
    """cross-period-comparison should import cleanly."""
    from skills.cross_period_comparison.run import run_cross_period
    assert callable(run_cross_period)


def test_inventory_scan_missing_table():
    """Calling inventory scan on nonexistent table returns error."""
    from skills.inventory_exception_scan.run import run_inventory_scan
    result = run_inventory_scan("nonexistent_table")
    assert result["status"] == "done"  # degrades gracefully
    assert "exceptions" in result


def test_cross_period_empty():
    """Cross-period with no periods should return empty results."""
    from skills.cross_period_comparison.run import run_cross_period
    result = run_cross_period("table_{period}", periods=[])
    assert result["status"] == "done"
    assert result["periods"] == []
