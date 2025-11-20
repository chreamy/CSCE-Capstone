import tkinter as tk
import unittest
from unittest import mock
from pathlib import Path
import tempfile

from frontend.parameter_selection import ParameterSelectionWindow
from backend.netlist_parse import Component


class DummyController:
    def __init__(self, initial=None):
        self.data = dict(initial or {})

    def get_app_data(self, key):
        return self.data.get(key)

    def update_app_data(self, key, value):
        self.data[key] = value

    def navigate(self, _):
        self.data["navigated"] = _


class DummyNetlist:
    def __init__(self, path):
        self.file_path = path
        self.components = [
            Component(name="VREF", type="R", scope="top"),
            Component(name="ILOAD", type="C", scope="top"),
            Component(name="V1", type="V", scope="top"),
            Component(name="I1", type="I", scope="top"),
        ]
        self.nodes = {"n1", "n2"}

    def resolve_include_paths(self):
        return []


class ParameterSelectionTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_persisted_selection_filters_sources_by_type(self):
        controller = DummyController(
            {
                "netlist_path": "dummy.cir",
                "selected_parameters": ["VREF", "ILOAD", "V1", "I1"],
            }
        )

        with mock.patch("frontend.parameter_selection.Netlist", DummyNetlist):
            window = ParameterSelectionWindow(self.root, controller)

        self.assertEqual(set(window.selected_parameters), {"VREF", "ILOAD"})
        self.assertEqual(set(window.available_parameters), {"VREF", "ILOAD"})
        self.assertEqual(set(window.sources), {"V1", "I1"})

    def test_gui_lists_show_only_non_source_components_from_netlist(self):
        netlist_text = "\n".join(
            [
                "* simple test netlist",
                "V1 in 0 DC 5",
                "I1 out 0 DC 1m",
                "RREF in out 10k",
                "CLOAD out 0 1n",
            ]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            netlist_path = Path(tmpdir) / "example.cir"
            netlist_path.write_text(netlist_text)
            controller = DummyController(
                {"netlist_path": str(netlist_path), "selected_parameters": []}
            )
            with mock.patch("frontend.parameter_selection.messagebox"):
                window = ParameterSelectionWindow(self.root, controller)
                window.update_selected_listbox()
                self.root.update_idletasks()

        available_items = set(window.available_listbox.get(0, tk.END))
        selected_items = set(window.selected_listbox.get(0, tk.END))
        self.assertEqual(available_items, {"RREF", "CLOAD"})
        self.assertEqual(selected_items, set())
        self.assertCountEqual(window.sources, ["V1", "I1"])


if __name__ == "__main__":
    unittest.main()
