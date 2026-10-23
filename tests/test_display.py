import unittest
from cat_analyst.display import primary_monitor, selection_region


class DisplayMappingTests(unittest.TestCase):
    def setUp(self):
        # Reproduce the reported arrangement: 125% secondary at index 1,
        # 100% primary at index 2. Qt selection is on the primary.
        self.monitors = [dict(left=-1920, top=0, width=3840, height=1130),
                         dict(left=-1920, top=50, width=1920, height=1080, is_primary=False),
                         dict(left=0, top=0, width=1920, height=1080, is_primary=True)]

    def test_secondary_first_never_offsets_primary_selection(self):
        region = selection_region(self.monitors, 1920, 1080, 409, 156, 1067, 924)
        self.assertEqual(region, dict(left=409, top=156, width=1067, height=924))
        self.assertNotEqual(region['left'], -1511)  # the actual broken draft value

    def test_high_dpi_primary_uses_its_own_physical_dimensions(self):
        region = selection_region(self.monitors, 1536, 864, 100, 80, 800, 600)
        self.assertEqual(region, dict(left=125, top=100, width=1000, height=750))

    def test_old_mss_without_primary_flag_uses_windows_origin(self):
        for monitor in self.monitors:
            monitor.pop('is_primary', None)
        self.assertEqual(primary_monitor(self.monitors)['left'], 0)
        self.assertEqual(primary_monitor(self.monitors)['width'], 1920)

    def test_virtual_desktop_is_not_a_candidate(self):
        monitors = [dict(left=0, top=0, width=3840, height=1080),
                    dict(left=1920, top=0, width=1920, height=1080),
                    dict(left=0, top=0, width=1920, height=1080)]
        self.assertEqual(primary_monitor(monitors)['width'], 1920)

    def test_unknown_primary_fails_instead_of_recording_another_display(self):
        with self.assertRaises(ValueError):
            primary_monitor([{}, dict(left=-1920, top=50, width=1920, height=1080)])

    def test_edges_are_clamped_and_empty_selection_rejected(self):
        region = selection_region(self.monitors, 1920, 1080, 1800, 1000, 300, 200)
        self.assertEqual(region, dict(left=1800, top=1000, width=120, height=80))
        with self.assertRaises(ValueError):
            selection_region(self.monitors, 1920, 1080, 2000, 0, 100, 100)


if __name__ == '__main__':
    unittest.main()
