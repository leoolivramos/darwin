import os
import tempfile
import pytest

from heuristics.base import RuleNotApplicable
from heuristics.timeout_rule import apply_timeout_rule
from heuristics.pool_size_rule import apply_pool_size_rule, apply_tomcat_threads
from heuristics.caching_rule import apply_caching_rule, cache_support_changes


def test_apply_timeout_rule_matches_regex():
    sample_code = """
    public void configureClient() {
        client.setTimeout(2000);
        client.setConnectTimeout(5000);
    }
    """
    with tempfile.NamedTemporaryFile("w+", suffix=".java", delete=False) as tmp:
        tmp.write(sample_code)
        tmp_path = tmp.name

    try:
        modified = apply_timeout_rule(tmp_path, factor=0.75)
        assert ".setTimeout(1500)" in modified
        assert ".setConnectTimeout(3750)" in modified
    finally:
        os.remove(tmp_path)


def test_apply_timeout_rule_not_applicable():
    sample_code = "public void doSomething() {}"
    with tempfile.NamedTemporaryFile("w+", suffix=".java", delete=False) as tmp:
        tmp.write(sample_code)
        tmp_path = tmp.name

    try:
        with pytest.raises(RuleNotApplicable):
            apply_timeout_rule(tmp_path)
    finally:
        os.remove(tmp_path)


def test_apply_pool_size_rule():
    sample_code = """
    public void configurePool() {
        dataSource.setMaxPoolSize(10);
    }
    """
    with tempfile.NamedTemporaryFile("w+", suffix=".java", delete=False) as tmp:
        tmp.write(sample_code)
        tmp_path = tmp.name

    try:
        modified = apply_pool_size_rule(tmp_path, increase_ratio=1.5)
        # 10 * 1.5 = 15, but min is 20
        assert "setMaxPoolSize(20)" in modified
    finally:
        os.remove(tmp_path)


def test_apply_caching_rule():
    sample_code = """
    public class UserService {
        public User findUserById(Long id) {
            return repo.findById(id);
        }
    }
    """
    with tempfile.NamedTemporaryFile("w+", suffix=".java", delete=False) as tmp:
        tmp.write(sample_code)
        tmp_path = tmp.name

    try:
        modified = apply_caching_rule(tmp_path)
        assert "@org.springframework.cache.annotation.Cacheable" in modified
        assert "findUserById" in modified
    finally:
        os.remove(tmp_path)
