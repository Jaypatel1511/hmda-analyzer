import pytest
from hmdaanalyzer.data.loader import load_sample


@pytest.fixture
def sample_df():
    return load_sample(n=2000, seed=42)


@pytest.fixture
def small_df():
    return load_sample(n=500, seed=42)
