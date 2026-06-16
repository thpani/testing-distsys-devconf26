import json
import tempfile
import unittest
from pathlib import Path

import visualize_dns_trace as viz


ROOT = Path(__file__).resolve().parents[1]
ROOT_NAME = "db.us-east-1.example.com"
ROLLBACK_NAME = "rollback.db.example.com"
LOCK_NAME = "lock.example.com"


def cname(name, target, weight=100):
    return {"kind": "CNAME", "name": name, "value": (target, weight)}


def a_record(name, ip):
    return {"kind": "A", "name": name, "value": (ip, 0)}


def lock(owner, epoch):
    return {"kind": "TXT", "name": LOCK_NAME, "value": (owner, epoch)}


TRACE = {
    "#meta": {"violation_step": 2},
    "vars": ["ghost_action"],
    "states": [
        {
            "#meta": {"step": 0},
            "zone_records": {
                "#set": [
                    lock("genesis", 0),
                    cname(ROOT_NAME, "plan-init.db.example.com", 1),
                    cname(ROLLBACK_NAME, "plan-init.db.example.com", 1),
                    cname("plan-init.db.example.com", "lb-1-init.db.example.com", 100),
                ]
            },
            "ghost_action": {"tag": "Init", "value": None},
        },
        {
            "#meta": {"step": 1},
            "zone_records": {
                "#set": [
                    lock("dep1", 1),
                    cname(ROOT_NAME, "plan4.db.example.com", 100),
                    cname(ROLLBACK_NAME, "plan-init.db.example.com", 1),
                    cname("plan-init.db.example.com", "lb-1-init.db.example.com", 100),
                    cname("plan4.db.example.com", "lb-2-4.db.example.com", 119),
                    a_record("lb-2-4.db.example.com", "192.0.2.2"),
                ]
            },
            "ghost_action": {
                "tag": "Deploy",
                "value": {
                    "deployer": "dep1",
                    "plan_id": "plan4.db.example.com",
                    "previous_root": "plan-init.db.example.com",
                    "new_root": "plan4.db.example.com",
                    "rollback": "plan-init.db.example.com",
                    "new_epoch": 1,
                },
            },
        },
        {
            "#meta": {"step": 2},
            "zone_records": {
                "#set": [
                    lock("dep1", 1),
                    cname(ROOT_NAME, "plan4.db.example.com", 100),
                    cname(ROLLBACK_NAME, "plan-init.db.example.com", 1),
                    cname("plan-init.db.example.com", "lb-1-init.db.example.com", 100),
                ]
            },
            "ghost_action": {
                "tag": "Cleanup",
                "value": {
                    "deployer": "dep1",
                    "next_plan": 5,
                    "old_indices": [0, 1],
                },
            },
        },
    ],
}


class VisualizeDnsTraceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.trace = TRACE
        cls.frames = viz.build_frames(cls.trace)

    def test_sample_trace_has_expected_frames_and_meta(self):
        self.assertEqual(len(self.frames), 3)
        self.assertEqual(self.trace["#meta"]["violation_step"], 2)
        self.assertIn("ghost_action", self.trace["vars"])

    def test_trace_actions_are_decoded(self):
        self.assertEqual(
            [frame["action"]["tag"] for frame in self.frames],
            [
                "Init",
                "Deploy",
                "Cleanup",
            ],
        )
        self.assertEqual(self.frames[0]["action"]["summary"], "Init")
        self.assertEqual(self.frames[1]["action"]["summary"], "Deploy dep1 -> plan4.ddb epoch 1")

    def test_current_action_names_are_decoded(self):
        generate = viz.decode_ghost_action(
            {
                "ghost_action": {
                    "tag": "GeneratePlan",
                    "value": {
                        "plan_id": "plan4.db.example.com",
                        "ips": ["192.0.2.2", "192.0.2.3"],
                        "weights": [("192.0.2.2", 119), ("192.0.2.3", 120)],
                    },
                }
            }
        )
        self.assertEqual(generate["summary"], "GeneratePlan plan4.ddb (2 IPs)")

        sync = viz.decode_ghost_action(
            {
                "ghost_action": {
                    "tag": "Sync",
                    "value": {
                        "deployer": "dep1",
                        "lock": {
                            "kind": "TXT",
                            "name": "lock.example.com",
                            "value": ("dep2", 2),
                        },
                        "root": "plan4.db.example.com",
                        "rollback": "plan-init.db.example.com",
                    },
                }
            }
        )
        self.assertEqual(sync["summary"], "Sync dep1 root plan4.ddb rollback plan-init.ddb")

        deploy = viz.decode_ghost_action(
            {
                "ghost_action": {
                    "tag": "Deploy",
                    "value": {
                        "deployer": "dep1",
                        "plan_id": "plan4.db.example.com",
                        "previous_root": "plan-init.db.example.com",
                        "new_root": "plan4.db.example.com",
                        "rollback": "plan-init.db.example.com",
                        "new_epoch": 1,
                    },
                }
            }
        )
        self.assertEqual(deploy["summary"], "Deploy dep1 -> plan4.ddb epoch 1")

        backoff = viz.decode_ghost_action(
            {
                "ghost_action": {
                    "tag": "Backoff",
                    "value": {
                        "deployer": "dep1",
                        "lock": {
                            "kind": "TXT",
                            "name": "lock.example.com",
                            "value": ("dep2", 2),
                        },
                    },
                }
            }
        )
        self.assertEqual(backoff["summary"], "Backoff dep1")

        cleanup = viz.decode_ghost_action(
            {
                "ghost_action": {
                    "tag": "Cleanup",
                    "value": {
                        "deployer": "dep1",
                        "next_plan": 5,
                        "old_indices": [0, 1],
                    },
                }
            }
        )
        self.assertEqual(cleanup["summary"], "Cleanup dep1 indices 0, 1")

    def test_state_root_and_rollback_targets(self):
        frame = self.frames[1]
        self.assertEqual(frame["rootTarget"], "plan4.db.example.com")
        self.assertEqual(frame["rollbackTarget"], "plan-init.db.example.com")
        self.assertFalse(next(plan["missing"] for plan in frame["plans"] if plan["id"] == frame["rootTarget"]))
        details = {item["label"]: item["value"] for item in frame["action"]["details"]}
        self.assertEqual(details["Previous"], "plan-init.ddb")
        self.assertEqual(details["Rollback"], "plan-init.ddb")

    def test_final_state_renders_broken_root_plan(self):
        final = self.frames[2]
        self.assertEqual(final["rootTarget"], "plan4.db.example.com")
        plan4 = next(plan for plan in final["plans"] if plan["id"] == "plan4.db.example.com")
        self.assertTrue(plan4["missing"])
        self.assertEqual(final["diff"]["added"], [])
        self.assertGreaterEqual(len(final["diff"]["removed"]), 1)
        self.assertTrue(any("plan4.ddb" in item for item in final["diff"]["removed"]))

    def test_generated_html_is_self_contained_viewer(self):
        html = viz.render_html(self.trace, self.frames, ROOT / "t.itf.json")
        self.assertIn("<svg id=\"graph\"", html)
        self.assertIn("const TRACE_DATA =", html)
        self.assertIn("playPause", html)
        self.assertIn("actionSummary", html)
        self.assertIn("<option value=\"90\">10x</option>", html)
        self.assertNotIn("https://", html)

    def test_load_trace_accepts_ndjson_and_trace_index(self):
        other_trace = {
            **TRACE,
            "#meta": {"example_step": 0},
            "states": [TRACE["states"][0]],
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "traces.ndjson"
            path.write_text(
                json.dumps(TRACE) + "\n" + json.dumps(other_trace) + "\n",
                encoding="utf-8",
            )

            self.assertEqual(
                viz.load_trace(path, trace_index=0)["#meta"]["violation_step"],
                2,
            )
            self.assertEqual(viz.load_trace(path, trace_index=1)["#meta"]["example_step"], 0)

    def test_load_trace_rejects_out_of_range_trace_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "trace.itf.json"
            path.write_text(json.dumps(TRACE), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "out of range"):
                viz.load_trace(path, trace_index=1)


if __name__ == "__main__":
    unittest.main()
