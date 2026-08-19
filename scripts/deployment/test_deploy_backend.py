import copy
import unittest

from deploy_backend import next_task_definition


class TaskDefinitionTests(unittest.TestCase):
    def test_replaces_image_version_and_removes_read_only_fields(self):
        current = {
            "family": "example-api",
            "revision": 4,
            "status": "ACTIVE",
            "taskDefinitionArn": "old",
            "cpu": "512",
            "containerDefinitions": [{
                "name": "api", "image": "old", "environment": [
                    {"name": "APP_VERSION", "value": "old"},
                    {"name": "APP_ENV", "value": "staging"},
                ],
            }],
        }
        original = copy.deepcopy(current)
        result = next_task_definition(current, "repo@sha256:" + "a" * 64, "abc123")
        self.assertNotIn("revision", result)
        self.assertNotIn("taskDefinitionArn", result)
        self.assertEqual(result["containerDefinitions"][0]["image"], "repo@sha256:" + "a" * 64)
        self.assertIn(
            {"name": "APP_VERSION", "value": "abc123"},
            result["containerDefinitions"][0]["environment"],
        )
        self.assertEqual(current, original)

    def test_rejects_ambiguous_multi_container_definition(self):
        with self.assertRaises(ValueError):
            next_task_definition(
                {"family": "x", "containerDefinitions": [{"name": "a"}, {"name": "b"}]},
                "image", "version",
            )


if __name__ == "__main__":
    unittest.main()
