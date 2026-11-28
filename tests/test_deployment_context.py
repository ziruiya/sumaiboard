"""Deployment context + auth pipeline invariants (spec 2, 4.3, 5).

Stdlib-only unit tests: deployment_context has no DB dependency; the auth
pipeline stage order is checked against the source as a static contract in
addition to the live-stack acceptance tests.
Run: python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class DeploymentContextRules(unittest.TestCase):
    def _load(self, env):
        for key in ("DEPLOYMENT_PROFILE", "DEPLOYMENT_ID", "DEPLOYMENT_TENANT_ID"):
            os.environ.pop(key, None)
        os.environ.update(env)
        for mod in list(sys.modules):
            if mod.startswith("backend.deployment_context"):
                del sys.modules[mod]
        import backend.deployment_context as dc
        return dc

    def test_missing_profile_is_fatal(self):
        dc = self._load({"DEPLOYMENT_ID": "x", "DEPLOYMENT_TENANT_ID": "1"})
        with self.assertRaises(Exception):
            dc.get_deployment_context()

    def test_sample_requires_tenant_1(self):
        dc = self._load({"DEPLOYMENT_PROFILE": "sample", "DEPLOYMENT_ID": "x",
                         "DEPLOYMENT_TENANT_ID": "17"})
        with self.assertRaises(Exception):
            dc.get_deployment_context()

    def test_product_accepts_tenant_17(self):
        dc = self._load({"DEPLOYMENT_PROFILE": "product", "DEPLOYMENT_ID": "x",
                         "DEPLOYMENT_TENANT_ID": "17"})
        ctx = dc.get_deployment_context()
        self.assertEqual(ctx.tenant_id, 17)
        self.assertEqual(dc.deployment_tenant_id(), 17)


class PipelineContract(unittest.TestCase):
    def test_pipeline_order_in_source(self):
        src = open(os.path.join(os.path.dirname(__file__), "..", "backend", "main.py"),
                   encoding="utf-8").read()
        fn = src[src.index("def _auth_pipeline_stage"):src.index("def _issue_session")]
        order = [fn.index('"MFA_CHALLENGE"'), fn.index('"GRANT_REQUIRED"'),
                 fn.index('"PASSWORD_CHANGE_REQUIRED"'), fn.index('"FULL"')]
        self.assertEqual(order, sorted(order),
                         "pipeline must evaluate MFA -> grant -> password change -> enrollment/FULL")


if __name__ == "__main__":
    unittest.main()
