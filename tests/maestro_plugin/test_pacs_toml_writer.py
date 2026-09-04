import unittest

from maestro_plugin.pacs_toml_writer import build_settings_dict, settings_dict_to_toml


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


class TestSettingsDictToToml(unittest.TestCase):
    def test_emits_section_headers_in_order(self):
        settings = build_settings_dict(
            structure_cms="system.cms",
            msj_file="production.msj",
            mdconf="production.cfg",
            working_dir="./run1",
            analyzer_type="rmsd",
            threshold=0.1,
            reference="ref.pdb",
            selection1="protein",
            selection2="protein",
        )
        toml_text = settings_dict_to_toml(settings)
        basic_idx = toml_text.index("## basic")
        simulator_idx = toml_text.index("## simulator")
        analyzer_idx = toml_text.index("## analyzer")
        postprocess_idx = toml_text.index("## postprocess")
        self.assertTrue(basic_idx < simulator_idx < analyzer_idx < postprocess_idx)

    def test_string_values_are_quoted(self):
        settings = build_settings_dict(
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
        toml_text = settings_dict_to_toml(settings)
        self.assertIn('simulator = "desmond"', toml_text)

    def test_numeric_and_bool_values_are_unquoted(self):
        settings = build_settings_dict(
            structure_cms="system.cms",
            msj_file="production.msj",
            mdconf="production.cfg",
            working_dir="./run1",
            analyzer_type="target",
            threshold=0.05,
            reference="ref.pdb",
            selection1="protein",
            selection2="protein",
            n_replica=20,
            centering=True,
        )
        toml_text = settings_dict_to_toml(settings)
        self.assertIn("n_replica = 20", toml_text)
        self.assertIn("centering = true", toml_text)


if __name__ == "__main__":
    unittest.main()
