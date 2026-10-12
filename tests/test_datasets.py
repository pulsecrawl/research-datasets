from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    value = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


class DatasetTests(unittest.TestCase):
    def test_counts_and_hashes(self):
        verifier = module("verify")
        self.assertEqual(verifier.verify_manifests(), {
            "fixed-html": 60, "site-pattern-html": 100, "commerce-html": 20,
        })
        verifier.privacy_scan()
        self.assertEqual((ROOT / "checksums.sha256").read_text(), verifier.checksum_lines())

    def test_fixed_inputs_regenerate_identically(self):
        generator = module("generate_fixed_html")
        for line in (ROOT / "datasets/fixed-html/manifest.jsonl").read_text().splitlines():
            row = json.loads(line)
            number = int(row["id"].split("-")[1])
            body, engine, mappings, truth = generator.document(row["vertical"], number, row["layout"])
            self.assertEqual(body.encode(), (ROOT / "datasets/fixed-html" / row["path"]).read_bytes())
            self.assertEqual((engine, mappings, truth), (row["engine"], row["mappings"], row["truth"]))

    def test_site_pattern_inputs_regenerate_identically(self):
        generator = module("generate_site_pattern")
        folder = ROOT / "datasets/site-pattern-html"
        sites = {s["id"]: s for s in json.loads((folder / "catalog.json").read_text())["sites"]}
        for line in (folder / "manifest.jsonl").read_text().splitlines():
            row = json.loads(line)
            number = int(row["id"].rsplit("-", 1)[1])
            body, truth = generator.render_fixture(sites[row["siteId"]], number)
            self.assertEqual(body.encode(), (folder / row["path"]).read_bytes())
            self.assertEqual(truth, row["truth"])

    def test_commerce_prices_are_fictional_and_repeat_scopes(self):
        generator = module("generate_commerce")
        folder = ROOT / "datasets/commerce-html"
        entries = [json.loads(line) for line in (folder / "manifest.jsonl").read_text().splitlines()]
        self.assertEqual(len({r["scopeUrl"] for r in entries}), 10)
        sources = {source.sample_url: source for source in generator.SOURCES}
        for row in entries:
            body = generator.product_html(sources[row["scopeUrl"]], row["observation"] - 1)
            self.assertEqual(body.encode(), (folder / row["path"]).read_bytes())
            self.assertFalse(row["liveEnabled"])
            self.assertEqual(row["truth"]["current_price"], 120.0 if row["observation"] == 1 else 99.0)

    def test_storage_sample_and_reference_config(self):
        folder = ROOT / "datasets/storage"
        config = json.loads((folder / "reference-config.json").read_text())
        self.assertEqual(config["totalRows"], 1000000)
        rows = []
        for path in sorted((folder / "sample").glob("*.jsonl")):
            rows.extend(json.loads(line) for line in path.read_text().splitlines())
        self.assertEqual(len(rows), 1000)
        self.assertEqual(len({r["_url_identity"] for r in rows}), 505)
        self.assertEqual(sum(r["_is_new_url"] for r in rows), 505)
        self.assertTrue(all(128 <= len(r["body"]) <= 2048 for r in rows))
        self.assertTrue(all(r["_source_url"].startswith("https://source.example/item/") for r in rows))

    def test_storage_generator_matches_sample(self):
        try:
            import duckdb
        except ImportError:
            self.skipTest("optional pinned storage dependency is not installed")
        generator = module("generate_storage")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "new"
            manifest = generator.generate(output, 1000, 2, format="jsonl")
            self.assertEqual(manifest["expectedDistinctUrlIdentities"], 505)
            for entry in manifest["files"]:
                self.assertEqual((output / entry["path"]).read_bytes(),
                                 (ROOT / "datasets/storage/sample" / entry["path"]).read_bytes())
            with self.assertRaises(FileExistsError):
                generator.generate(output, 1000, 2)

    def test_webbench_uses_loopback_http(self):
        webbench = module("webbench")
        with webbench.WebBenchServer(webbench.WebBenchConfig(items_per_site=2, sites_per_vertical=1)) as server:
            self.assertTrue(server.base_url.startswith("http://127.0.0.1:"))
            with urlopen(server.base_url + "/robots.txt", timeout=5) as response:
                self.assertEqual(response.status, 200)
                self.assertIn(b"User-agent:", response.read())


if __name__ == "__main__":
    unittest.main()
