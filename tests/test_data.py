from nil_predictor.data import DataConfig, FEATURE_COLUMNS, TARGET_COLUMNS, generate


def test_generate_is_deterministic():
    a = generate(DataConfig(n_athletes=200, seed=42))
    b = generate(DataConfig(n_athletes=200, seed=42))
    assert a.equals(b)


def test_generate_shape_and_columns():
    df = generate(DataConfig(n_athletes=300, seed=1))
    assert len(df) == 300
    for col in FEATURE_COLUMNS + TARGET_COLUMNS:
        assert col in df.columns


def test_valuation_distribution_is_heavy_tailed():
    df = generate(DataConfig(n_athletes=2000, seed=3))
    # Median should be well below mean — that's the heavy right tail.
    assert df["nil_valuation_usd"].median() < df["nil_valuation_usd"].mean()
    assert df["nil_valuation_usd"].max() > df["nil_valuation_usd"].median() * 50


def test_tier_has_all_levels():
    df = generate(DataConfig(n_athletes=2000, seed=4))
    assert set(df["tier"].unique()) >= {"low", "mid", "high"}
