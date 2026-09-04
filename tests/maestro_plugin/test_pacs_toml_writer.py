import unittest

from maestro_plugin.pacs_toml_writer import build_settings_dict


class TestBuildSettingsDict(unittest.TestCase):
    def _required_kwargs(self, **overrides):
        kwargs = dict(
            structure_cms="system.cms",
            msj_file="production.msj",
            mdconf="production.cfg",
            working_dir="./run1",
            analyzer_type="target",
            threshold=0.05,
            reference="ref.pdb",
            selection1="protein",
            selection2="protein",
        )
        kwargs.update(overrides)
        return kwargs

    def test_fixed_engine_fields(self):
        settings = build_settings_dict(**self._required_kwargs())
        self.assertEqual(settings["simulator"], "desmond")
        self.assertEqual(settings["analyzer"], "desmond")
        self.assertEqual(settings["trajectory_extension"], ".dtr")

    def test_structure_and_topology_share_the_same_cms(self):
        settings = build_settings_dict(**self._required_kwargs(structure_cms="foo.cms"))
        self.assertEqual(settings["structure"], "foo.cms")
        self.assertEqual(settings["topology"], "foo.cms")

    def test_rejects_unsupported_analyzer_type(self):
        with self.assertRaises(ValueError):
            build_settings_dict(**self._required_kwargs(analyzer_type="dissociation"))


if __name__ == "__main__":
    unittest.main()
