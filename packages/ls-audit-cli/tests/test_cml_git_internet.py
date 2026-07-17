import base64
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import cml_git_internet as cml
import ls_audit as core
import ls_audit_cml_cli as integration

HEAD = "a" * 40
BASE = "b" * 40
MEMORY_SOURCE = "c" * 40
PIN = "d" * 40


def make_pack(
    repository: str = "acme/cml",
    *,
    visibility: str = "public",
    private_data: bool = False,
    situation: str = "GitHub workflow permissions blocked pull request creation",
) -> dict[str, Any]:
    pack: dict[str, Any] = {
        "schema_version": "cml-memory-pack-v1",
        "pack_id": "",
        "manifest": {
            "project": "CML",
            "source_repository": f"https://github.com/{repository}",
            "source_commit": MEMORY_SOURCE,
            "created_at": "2026-07-17T00:00:00.000Z",
            "visibility": visibility,
            "license": "Apache-2.0",
            "contains_private_data": private_data,
            "merge_authority": False,
            "execution_authority": False,
            "description": "Exact-base GitHub workflow recovery lesson",
        },
        "graph": {
            "nodes": [
                {
                    "id": "n1",
                    "kind": "situation",
                    "label": situation,
                    "status": "accepted",
                    "confidence": 1.0,
                    "attributes": {},
                },
                {
                    "id": "n2",
                    "kind": "action",
                    "label": "Use an exact generated branch and permission fallback",
                    "status": "accepted",
                    "confidence": 1.0,
                    "attributes": {},
                },
                {
                    "id": "n3",
                    "kind": "lesson",
                    "label": "Validate GitHub permissions with a live exact-base proof",
                    "status": "accepted",
                    "confidence": 1.0,
                    "attributes": {},
                },
                {
                    "id": "n4",
                    "kind": "constraint",
                    "label": "Memory grants no merge or execution authority",
                    "status": "accepted",
                    "confidence": 1.0,
                    "attributes": {},
                },
            ],
            "edges": [
                {
                    "id": "e1",
                    "source": "n1",
                    "target": "n2",
                    "relation": "resolved_by",
                    "strength": 1.0,
                    "evidence_ids": ["ev1"],
                },
                {
                    "id": "e2",
                    "source": "n2",
                    "target": "n3",
                    "relation": "produced",
                    "strength": 1.0,
                    "evidence_ids": ["ev1"],
                },
            ],
            "selected_path": ["n1", "n2", "n3"],
        },
        "evidence": [
            {
                "id": "ev1",
                "kind": "github",
                "digest": "sha256:" + "e" * 64,
                "locator": "https://github.com/acme/cml/pull/1",
                "description": "CI and a live GitHub workflow proof passed",
            }
        ],
        "redactions": [],
    }
    pack["pack_id"] = cml.sha256_json(cml._canonical_preimage(pack))
    return pack


class FakeClient:
    def __init__(self, packs: dict[str, dict[str, Any]], *, fail: bool = False) -> None:
        self.packs = packs
        self.fail = fail
        self.calls: list[str] = []

    def get(self, endpoint: str) -> Any:
        self.calls.append(endpoint)
        if self.fail:
            raise RuntimeError("private provider detail")
        if endpoint == "/repos/acme/cml":
            return {"private": False}
        if endpoint == f"/repos/acme/cml/contents/.cml/memory/cycles?ref={PIN}":
            return [
                {"type": "file", "path": path}
                for path in reversed(sorted(self.packs))
            ]
        prefix = "/repos/acme/cml/contents/"
        if endpoint.startswith(prefix) and endpoint.endswith(f"?ref={PIN}"):
            path = endpoint[len(prefix) : -len(f"?ref={PIN}")]
            raw = json.dumps(self.packs[path]).encode("utf-8")
            return {
                "encoding": "base64",
                "size": len(raw),
                "content": base64.b64encode(raw).decode("ascii"),
            }
        raise AssertionError(endpoint)


class RegistryTests(unittest.TestCase):
    def test_registry_requires_exact_public_git_source_pin(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "registry.json"
            path.write_text(
                json.dumps(
                    {
                        "schema_version": cml.REGISTRY_SCHEMA,
                        "sources": [{"repository": "acme/cml", "commit": PIN}],
                    }
                )
            )
            registry = cml.load_registry(path)
            self.assertEqual(registry.sources, (cml.Source("acme/cml", PIN),))

            path.write_text(
                json.dumps(
                    {
                        "schema_version": cml.REGISTRY_SCHEMA,
                        "sources": [{"repository": "acme/cml", "commit": "main"}],
                    }
                )
            )
            with self.assertRaises(cml.CmlError):
                cml.load_registry(path)

    def test_duplicate_registry_source_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "registry.json"
            source = {"repository": "acme/cml", "commit": PIN}
            path.write_text(
                json.dumps(
                    {"schema_version": cml.REGISTRY_SCHEMA, "sources": [source, source]}
                )
            )
            with self.assertRaises(cml.CmlError):
                cml.load_registry(path)


class PackTests(unittest.TestCase):
    def test_canonical_identity_and_graph_are_independently_verified(self) -> None:
        pack = make_pack()
        text = json.dumps(pack)
        document = cml.parse_memory_pack(
            text,
            path=f"{cml.MEMORY_ROOT}/public.json",
            source_repository="acme/cml",
            registry_commit=PIN,
        )
        self.assertIsNotNone(document)
        self.assertEqual(document.pack_id, pack["pack_id"])

        pack["graph"]["nodes"][0]["label"] = "tampered"
        with self.assertRaises(cml.CmlError):
            cml.parse_memory_pack(
                json.dumps(pack),
                path=f"{cml.MEMORY_ROOT}/public.json",
                source_repository="acme/cml",
                registry_commit=PIN,
            )

    def test_non_public_memory_is_validated_but_not_publishable(self) -> None:
        pack = make_pack(visibility="team", private_data=True)
        document = cml.parse_memory_pack(
            json.dumps(pack),
            path=f"{cml.MEMORY_ROOT}/team.json",
            source_repository="acme/cml",
            registry_commit=PIN,
        )
        self.assertIsNone(document)

    def test_authority_claim_is_rejected(self) -> None:
        pack = make_pack()
        pack["manifest"]["merge_authority"] = True
        pack["pack_id"] = cml.sha256_json(cml._canonical_preimage(pack))
        with self.assertRaises(cml.CmlError):
            cml.parse_memory_pack(
                json.dumps(pack),
                path=f"{cml.MEMORY_ROOT}/authority.json",
                source_repository="acme/cml",
                registry_commit=PIN,
            )


class RetrievalTests(unittest.TestCase):
    def registry(self) -> cml.Registry:
        return cml.Registry((cml.Source("acme/cml", PIN),))

    def target(self) -> dict[str, str]:
        return {
            "pr_url": "https://github.com/acme/app/pull/7",
            "expected_head": HEAD,
            "base_sha": BASE,
        }

    def test_public_memory_is_ranked_and_private_memory_is_not_disclosed(self) -> None:
        public_path = f"{cml.MEMORY_ROOT}/public.json"
        private_path = f"{cml.MEMORY_ROOT}/team.json"
        client = FakeClient(
            {
                public_path: make_pack(),
                private_path: make_pack(visibility="team", private_data=True),
            }
        )
        evidence = cml.collect_evidence(
            registry=self.registry(),
            client=client,
            target=self.target(),
            title="Fix GitHub workflow permissions with exact-base fallback",
            filenames=[".github/workflows/review.yml"],
        )

        self.assertEqual(evidence["lane_status"], "PASS")
        self.assertEqual(evidence["publishable_candidates"], 1)
        self.assertEqual(len(evidence["selected"]), 1)
        self.assertEqual(evidence["selected"][0]["path"], public_path)
        self.assertFalse(any(evidence["authority"].values()))
        serialized = json.dumps(evidence)
        self.assertNotIn("withheld", serialized)
        self.assertNotIn(private_path, serialized)

    def test_source_failure_is_generic_incomplete_evidence(self) -> None:
        evidence = cml.collect_evidence(
            registry=self.registry(),
            client=FakeClient({}, fail=True),
            target=self.target(),
            title="workflow permission",
            filenames=[],
        )
        self.assertEqual(evidence["lane_status"], "INCOMPLETE")
        self.assertEqual(evidence["sources"][0]["reason_code"], "SOURCE_INCOMPLETE")
        self.assertNotIn("provider detail", json.dumps(evidence))

    def test_source_order_does_not_control_ranking(self) -> None:
        first = cml.MemoryDocument(
            source_repository="z/repo",
            registry_commit=PIN,
            path=f"{cml.MEMORY_ROOT}/z.json",
            pack_id="f" * 64,
            source_commit=MEMORY_SOURCE,
            situation="workflow permission fallback",
            selected_path=("workflow permission fallback", "exact base lesson"),
            constraints=(),
            token_weights={"workflow": 5, "permission": 5, "fallback": 5},
            evidence_count=1,
        )
        second = cml.MemoryDocument(
            source_repository="a/repo",
            registry_commit=PIN,
            path=f"{cml.MEMORY_ROOT}/a.json",
            pack_id="0" * 64,
            source_commit=MEMORY_SOURCE,
            situation="workflow permission fallback",
            selected_path=("workflow permission fallback", "exact base lesson"),
            constraints=(),
            token_weights={"workflow": 5, "permission": 5, "fallback": 5},
            evidence_count=1,
        )
        query = cml.build_query_weights(
            title="workflow permission fallback", filenames=[]
        )
        forward = cml.retrieve(query, [first, second])
        reverse = cml.retrieve(query, [second, first])
        self.assertEqual(
            [item.document.pack_id for item in forward],
            [item.document.pack_id for item in reverse],
        )
        self.assertEqual(forward[0].document.pack_id, "0" * 64)


class ScorecardTests(unittest.TestCase):
    def write_bundle(self, root: Path, *, human: dict[str, Any] | None = None) -> None:
        (root / "evidence").mkdir()
        card = {
            "schema_version": core.SCHEMA,
            "generated_at": "2026-07-17T00:00:00Z",
            "target": {
                "pr_url": "https://github.com/acme/app/pull/7",
                "expected_head": HEAD,
                "observed_head": HEAD,
            },
            "verdict": "INCOMPLETE — HUMAN ADJUDICATION REQUIRED",
            "lanes": {
                "exact_head": "PASS",
                "final_exact_head": "PASS",
                "human_adjudication": "PASS" if human else "NOT_RUN",
            },
            "interpretation": "existing",
            "evidence_digests": {},
            "bundle_digest": "sha256:" + "0" * 64,
            "authority": "advisory-only",
            "adjudication": human,
        }
        (root / "scorecard.json").write_text(json.dumps(card))
        (root / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": core.SCHEMA,
                    "authority": "advisory-only",
                    "evidence_digests": {},
                }
            )
        )

    def evidence(self, lane: str = "PASS") -> dict[str, Any]:
        return {
            "lane_status": lane,
            "sources": [{"repository": "acme/cml", "commit": PIN}],
            "publishable_candidates": 0,
            "selected": [],
            "authority": {
                "approval": False,
                "execution": False,
                "delivery": False,
                "merge": False,
            },
        }

    def test_cml_is_bound_into_scorecard_and_cannot_create_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_bundle(root)
            prior = core.Result(root, "INCOMPLETE", "PASS", 0)
            result = integration.attach_cml_to_scorecard(
                output=root,
                cml_evidence=self.evidence(),
                cml_digest="1" * 64,
                prior_result=prior,
            )
            card = json.loads((root / "scorecard.json").read_text())
            manifest = json.loads((root / "manifest.json").read_text())
            self.assertEqual(card["lanes"]["causal_memory"], "PASS")
            self.assertIn("HUMAN ADJUDICATION", result.verdict)
            self.assertEqual(
                manifest["evidence_digests"]["evidence/cml-memory.json"],
                "1" * 64,
            )
            self.assertIn("## Causal Memory", (root / "SCORECARD.md").read_text())
            self.assertIn("scorecard_digests", manifest)

    def test_incomplete_cml_lane_requires_explicit_human_acceptance(self) -> None:
        human = {
            "decision": "PASS",
            "accepted_incomplete_lanes": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_bundle(root, human=human)
            result = integration.attach_cml_to_scorecard(
                output=root,
                cml_evidence=self.evidence("INCOMPLETE"),
                cml_digest="2" * 64,
                prior_result=core.Result(root, "PASS", "PASS", 0),
            )
            self.assertEqual(
                result.verdict,
                "INCONCLUSIVE — UNACCEPTED INCOMPLETE EVIDENCE",
            )

    def test_cross_repo_client_is_anonymous(self) -> None:
        client = integration.anonymous_cml_client(1.0)
        self.assertIsNone(client.token)
        self.assertEqual(client.base, "https://api.github.com")


if __name__ == "__main__":
    unittest.main()
