import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from metricagent.access import User
from metricagent.agent import Agent
from metricagent.data import build
from metricagent.planner import RulePlanner
from metricagent.semantic import Layer


@pytest.fixture(scope="session")
def db():
    return build()


@pytest.fixture(scope="session")
def layer():
    return Layer()


@pytest.fixture
def agent(db, layer):
    return Agent(db, layer, RulePlanner(layer, db))


@pytest.fixture
def admin():
    return User("admin", "admin")


@pytest.fixture
def odense():
    return User("odense", "store_manager", ("S06",))
