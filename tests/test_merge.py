import unittest
import os
import datetime
import importlib.util

# Load tapo-cli module dynamically
script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tapo-cli.py'))
spec = importlib.util.spec_from_file_location("tapo_cli", script_path)
tapo_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tapo_cli)

class TestVideoMerge(unittest.TestCase):

    def test_parse_clip_timestamp(self):
        """Test extracting datetime from clip filename."""
        t1 = tapo_cli.parse_clip_timestamp("2026-09-05 09-48-35.mp4")
        self.assertEqual(t1, datetime.datetime(2026, 9, 5, 9, 48, 35))

        t2 = tapo_cli.parse_clip_timestamp("2026-09-05 18-47-23_abcd1234.mp4")
        self.assertEqual(t2, datetime.datetime(2026, 9, 5, 18, 47, 23))

        t_none = tapo_cli.parse_clip_timestamp("random_video.mp4")
        self.assertIsNone(t_none)

    def test_group_continuous_clips(self):
        """Test grouping clips whose gaps are <= max_gap seconds."""
        # 3 clips continuous (each 60s, gap=0s)
        # 4th clip after 3 hours
        # 5th clip 5s after 4th clip
        base = datetime.datetime(2026, 9, 5, 10, 0, 0)
        clips = [
            {'path': 'clip1.mp4', 'start_time': base, 'duration': 60.0, 'end_time': base + datetime.timedelta(seconds=60)},
            {'path': 'clip2.mp4', 'start_time': base + datetime.timedelta(seconds=60), 'duration': 60.0, 'end_time': base + datetime.timedelta(seconds=120)},
            {'path': 'clip3.mp4', 'start_time': base + datetime.timedelta(seconds=125), 'duration': 60.0, 'end_time': base + datetime.timedelta(seconds=185)}, # 5s gap
            {'path': 'clip4.mp4', 'start_time': base + datetime.timedelta(hours=3), 'duration': 60.0, 'end_time': base + datetime.timedelta(hours=3, seconds=60)}, # 3h gap
            {'path': 'clip5.mp4', 'start_time': base + datetime.timedelta(hours=3, seconds=70), 'duration': 60.0, 'end_time': base + datetime.timedelta(hours=3, seconds=130)}, # 10s gap
        ]

        # With max_gap = 10s:
        # Group 1: clip1, clip2, clip3 (gaps: 0s, 5s <= 10s)
        # Group 2: clip4, clip5 (gap: 10s <= 10s)
        groups = tapo_cli.group_continuous_clips(clips, max_gap_seconds=10)
        self.assertEqual(len(groups), 2)
        self.assertEqual(len(groups[0]), 3)
        self.assertEqual(len(groups[1]), 2)

        # With default max_gap (60s):
        # Group 1: clip1, clip2, clip3 (gap 5s <= 60s)
        # Group 2: clip4, clip5 (gap 10s <= 60s)
        groups_default = tapo_cli.group_continuous_clips(clips)
        self.assertEqual(len(groups_default), 2)
        self.assertEqual(len(groups_default[0]), 3)
        self.assertEqual(len(groups_default[1]), 2)

if __name__ == '__main__':
    unittest.main()
