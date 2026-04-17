from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = (
    Path(__file__).resolve().parents[1]
    / "financial-analysis"
    / "skills"
    / "month-end-shortlist"
    / "scripts"
)
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import macro_health_assisted_shortlist as module_under_test


class MacroHealthAssistedShortlistTests(unittest.TestCase):
    def test_parse_args_allows_omitting_macro_request(self) -> None:
        args = module_under_test.parse_args(["base.json"])
        self.assertEqual(args.shortlist_request_json, "base.json")
        self.assertEqual(args.macro_health_request_json, "")

    def test_default_macro_request_template_exists(self) -> None:
        self.assertTrue(module_under_test.DEFAULT_MACRO_HEALTH_REQUEST.exists())

    def test_main_uses_default_macro_request_when_omitted(self) -> None:
        loaded_paths: list[Path] = []
        writes: list[tuple[Path, dict]] = []

        def fake_load_json(path: Path) -> dict:
            loaded_paths.append(path)
            if path == Path("C:/base.json"):
                return {"template_name": "month_end_shortlist"}
            if path == module_under_test.DEFAULT_MACRO_HEALTH_REQUEST:
                return {"live_data_provider": "public_macro_mix"}
            raise AssertionError(path)

        def fake_build_macro_health_overlay_result(request: dict) -> dict:
            self.assertEqual(request["live_data_provider"], "public_macro_mix")
            return {"macro_health_overlay": {"health_label": "mixed_or_neutral_window"}}

        def fake_run_month_end_shortlist(request: dict) -> dict:
            self.assertEqual(request["macro_health_overlay"]["health_label"], "mixed_or_neutral_window")
            return {"request": request, "report_markdown": "# ok\n"}

        def fake_write_json(path: Path, payload: dict) -> None:
            writes.append((path, payload))

        with patch.object(module_under_test, "load_json", side_effect=fake_load_json), patch.object(
            module_under_test, "build_macro_health_overlay_result", side_effect=fake_build_macro_health_overlay_result
        ), patch.object(module_under_test, "run_month_end_shortlist", side_effect=fake_run_month_end_shortlist), patch.object(
            module_under_test, "write_json", side_effect=fake_write_json
        ):
            exit_code = module_under_test.main(
                ["C:/base.json", "--output", "C:/out.json", "--overlay-output", "C:/overlay.json", "--resolved-request-output", "C:/resolved.json"]
            )

        self.assertEqual(exit_code, 0)
        self.assertEqual(loaded_paths[0], Path("C:/base.json"))
        self.assertEqual(loaded_paths[1], module_under_test.DEFAULT_MACRO_HEALTH_REQUEST)
        self.assertEqual(len(writes), 3)

    def test_main_can_also_merge_sentiment_overlay_when_requested(self) -> None:
        loaded_paths: list[Path] = []
        writes: list[tuple[Path, dict]] = []

        def fake_load_json(path: Path) -> dict:
            loaded_paths.append(path)
            if path == Path("C:/base.json"):
                return {"template_name": "month_end_shortlist"}
            if path == module_under_test.DEFAULT_MACRO_HEALTH_REQUEST:
                return {"live_data_provider": "public_macro_mix"}
            if path == Path("C:/sentiment.json"):
                return {"broad_iv_percentile": 44.0, "growth_iv_percentile": 94.0, "skew_percentile": 90.0}
            raise AssertionError(path)

        def fake_build_macro_health_overlay_result(request: dict) -> dict:
            return {"macro_health_overlay": {"health_label": "mixed_or_neutral_window"}}

        def fake_build_a_share_sentiment_overlay_result(request: dict) -> dict:
            self.assertEqual(request["growth_iv_percentile"], 94.0)
            return {"sentiment_vol_overlay": {"sentiment_regime": "panic_in_growth_not_broad_market"}}

        def fake_run_month_end_shortlist(request: dict) -> dict:
            self.assertEqual(request["macro_health_/**
 * createVariableCollection
 *
 * Creates a new Figma variable collection with the specified name and modes.
 * If `modeNames` has more than one entry, the first mode is renamed from
 * Figma's default "Mode 1" to the first name, and additional modes are added.
 *
 * Every created collection is tagged with `dsb_key` plugin data so it can be
 * found and cleaned up idempotently by `cleanupOrphans`.
 *
 * @param {string} name - The display name of the collection (e.g. "Color", "Spacing").
 * @param {string[]} modeNames - Ordered list of mode names (e.g. ["Light", "Dark"] or ["Value"]).
 * @param {string} [runId] - Optional dsb_run_id to tag for cleanup.
 * @returns {Promise<{
 *   collection: VariableCollection,
 *   modeIds: Record<string, string>
 * }>}
 *   `modeIds` maps each mode name to its modeId string.
 */
async function createVariableCollection(name, modeNames, runId) {
  if (!modeNames || modeNames.length === 0) {
    throw new Error('createVariableCollection: modeNames must have at least one entry.')
  }

  // Create the collection — Figma always creates it with one mode named "Mode 1".
  const collection = figma.variables.createVariableCollection(name)

  // Tag for idempotent cleanup
  collection.setPluginData('dsb_key', `collection/${name}`)
  if (runId) {
    collection.setPluginData('dsb_run_id', runId)
  }

  // modeIds accumulator
  const modeIds = {}

  // Rename the default first mode
  const defaultMode = collection.modes[0]
  collection.renameMode(defaultMode.modeId, modeNames[0])
  modeIds[modeNames[0]] = defaultMode.modeId

  // Add additional modes
  for (let i = 1; i < modeNames.length; i++) {
    const newModeId = collection.addMode(modeNames[i])
    modeIds[modeNames[i]] = newModeId
  }

  return { collection, modeIds }
}
