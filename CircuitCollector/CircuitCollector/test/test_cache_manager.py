"""
Test CacheManager initialization and basic operations.
"""
from pathlib import Path
from CircuitCollector.cache import CacheManager
from CircuitCollector.utils.path import PROJECT_ROOT


def test_cache_manager_init():
    """Test CacheManager initialization."""
    cm = CacheManager()
    
    # Check Redis connection
    assert cm.redis_client is not None
    cm.redis_client.ping()  # Should not raise exception
    
    # Check SQLite path
    expected_path = PROJECT_ROOT / "database" / "cache.db"
    assert cm.sqlite_path == expected_path
    assert cm.sqlite_path.parent.exists()  # database folder should exist
    
    # Check statistics initialized
    assert "redis_hit" in cm.stats
    assert "redis_miss" in cm.stats
    assert "sqlite_hit" in cm.stats
    assert "sqlite_miss" in cm.stats
    assert "set_count" in cm.stats


def test_table_name_generation():
    """Test table name generation from circuit path."""
    cm = CacheManager()
    
    # Test various circuit paths
    assert cm._get_table_name("config/skywater/opamp/tsm.toml") == "skywater_opamp_tsm"
    assert cm._get_table_name("config/skywater/opamp/5tota.toml") == "skywater_opamp_5tota"
    assert cm._get_table_name("config/skywater/ldo/ldo1.toml") == "skywater_ldo_ldo1"


def test_table_creation():
    """Test that tables are created on demand."""
    cm = CacheManager()
    circuit = "config/skywater/opamp/tsm.toml"
    
    # Ensure table exists
    cm._ensure_table(circuit)
    
    # Check table exists in database
    import sqlite3
    conn = sqlite3.connect(cm.sqlite_path)
    cursor = conn.cursor()
    table_name = cm._get_table_name(circuit)
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table_name,)
    )
    result = cursor.fetchone()
    conn.close()
    
    assert result is not None
    assert result[0] == table_name


def test_key_generation():
    """Test canonical key generation."""
    cm = CacheManager()
    
    circuit = "config/skywater/opamp/tsm.toml"
    params1 = {"M1_L": 0.15, "M1_W": 0.5}
    params2 = {"M1_W": 0.5, "M1_L": 0.15}  # Same params, different order
    
    key1 = cm._generate_key(circuit, params1)
    key2 = cm._generate_key(circuit, params2)
    
    # Keys should be the same regardless of param order
    assert key1 == key2
    
    # Different params should produce different keys
    params3 = {"M1_L": 0.16, "M1_W": 0.5}
    key3 = cm._generate_key(circuit, params3)
    assert key1 != key3


def test_cache_set_get():
    """Test basic cache set and get operations."""
    cm = CacheManager()
    
    circuit = "config/skywater/opamp/tsm.toml"
    params = {"M1_L": 0.15, "M1_W": 0.5}
    value = {
        "circuit": circuit,
        "params": params,
        "specs": {"dcgain_": 60.5},
        "op_region": {"m1": {"gm": 0.001}},
        "raw": {},
    }
    
    # Set value
    cm.set(circuit, params, value)
    
    # Get value
    cached = cm.get(circuit, params)
    
    assert cached is not None
    assert cached["circuit"] == circuit
    assert cached["specs"]["dcgain_"] == 60.5


if __name__ == "__main__":
    # Run tests
    test_cache_manager_init()
    print("✓ CacheManager initialization test passed")
    
    test_table_name_generation()
    print("✓ Table name generation test passed")
    
    test_table_creation()
    print("✓ Table creation test passed")
    
    test_key_generation()
    print("✓ Key generation test passed")
    
    test_cache_set_get()
    print("✓ Cache set/get test passed")
    
    print("\nAll tests passed!")

