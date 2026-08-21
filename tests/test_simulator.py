from app.models.domain import MarketRegime
from app.simulator.market import MarketSimulator
from app.simulator.scenarios import PRESET_SCENARIOS, load_scenario


def test_market_simulator_determinism():
    config = PRESET_SCENARIOS["normal"]
    sim1 = MarketSimulator(config, override_seed=123)
    path1 = sim1.generate_market_path()

    sim2 = MarketSimulator(config, override_seed=123)
    path2 = sim2.generate_market_path()

    assert len(path1) == len(path2)
    for t1, t2 in zip(path1, path2):
        assert t1.mid_price == t2.mid_price
        assert t1.bid_price == t2.bid_price
        assert t1.ask_price == t2.ask_price
        assert t1.volume == t2.volume
        assert t1.volatility == t2.volatility


def test_volatility_shock_scenario():
    config = load_scenario("volatility_shock")
    sim = MarketSimulator(config, override_seed=42)
    path = sim.generate_market_path()

    pre_shock = [t for t in path if t.timestamp < config.shock_timestamp]
    post_shock = [t for t in path if t.timestamp >= config.shock_timestamp]

    assert len(pre_shock) > 0
    assert len(post_shock) > 0

    # Volatility and spread should be higher post shock
    assert post_shock[0].volatility > pre_shock[0].volatility
    assert post_shock[0].regime in (MarketRegime.VOLATILITY_SHOCK, MarketRegime.COMBINED_SHOCK)


def test_liquidity_shock_scenario():
    config = load_scenario("liquidity_shock")
    sim = MarketSimulator(config, override_seed=42)
    path = sim.generate_market_path()

    post_shock = [t for t in path if t.timestamp >= config.shock_timestamp]
    assert post_shock[0].liquidity < config.liquidity
    assert post_shock[0].regime in (MarketRegime.LIQUIDITY_SHOCK, MarketRegime.COMBINED_SHOCK)
