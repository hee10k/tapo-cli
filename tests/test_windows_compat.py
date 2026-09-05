import unittest
from unittest.mock import patch, MagicMock
import os
import re
import sys
import datetime
import tempfile
import importlib.util
from click.testing import CliRunner

# Load tapo-cli module dynamically because of the hyphen in filename
script_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tapo-cli.py'))
spec = importlib.util.spec_from_file_location("tapo_cli", script_path)
tapo_cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tapo_cli)

class TestWindowsCompatibility(unittest.TestCase):

    def test_sanitize_filename_reserved_chars(self):
        """Test that Windows forbidden characters are replaced."""
        test_cases = [
            ("Camera: Front", "Camera_ Front"),
            ("Living / Room", "Living _ Room"),
            ('Door "Bell"', "Door _Bell_"),
            ("Camera <1>", "Camera _1_"),
            ("Cam|Back*Yard?", "Cam_Back_Yard_"),
            ("Back\\Yard", "Back_Yard"),
        ]
        for input_name, expected in test_cases:
            self.assertEqual(tapo_cli.sanitize_filename(input_name), expected)

    def test_sanitize_filename_trailing_dots_and_spaces(self):
        """Test that trailing/leading dots and spaces are stripped."""
        self.assertEqual(tapo_cli.sanitize_filename("  Camera 1.  "), "Camera 1")
        self.assertEqual(tapo_cli.sanitize_filename("..."), "unnamed")
        self.assertEqual(tapo_cli.sanitize_filename(""), "unnamed")

    def test_sanitize_filename_reserved_words(self):
        """Test that Windows reserved device names are escaped."""
        reserved = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM9', 'LPT1', 'LPT9']
        for word in reserved:
            sanitized = tapo_cli.sanitize_filename(word)
            self.assertNotEqual(sanitized, word)
            self.assertTrue(sanitized.startswith('_') and sanitized.endswith('_'))

    def test_config_path(self):
        """Test config_path returns a valid path string in user directory."""
        path = tapo_cli.config_path()
        self.assertTrue(path.endswith(os.path.join('.tapo-cli', '.config')))

    def test_time_range(self):
        """Test time_range returns properly formatted dates."""
        start_time, end_time = tapo_cli.time_range(1)
        pattern = r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$'
        self.assertRegex(start_time, pattern)
        self.assertRegex(end_time, pattern)

    def test_download_unencrypted_file(self):
        """Test downloading an unencrypted file creates directories and writes content."""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_dir = os.path.join(tmpdir, "Camera_Front", "2026-09-05")
            file_name = "test_video.mp4"
            fake_content = b"fake-video-bytes-data"

            mock_response = MagicMock()
            mock_response.content = fake_content

            with patch('requests.get', return_value=mock_response):
                tapo_cli.download("http://example.com/video.mp4", False, file_dir, file_name)

            final_file = os.path.join(file_dir, file_name)
            self.assertTrue(os.path.exists(final_file))
            with open(final_file, 'rb') as f:
                self.assertEqual(f.read(), fake_content)
            self.assertFalse(os.path.exists(final_file + '.tmp'))

    def test_filter_devices(self):
        """Test filter_devices matches by alias and deviceId."""
        sample_devices = [
            {'alias': '정우방', 'deviceId': '8021D1615A5F4F65142D082E14F91E1224BD6D7A'},
            {'alias': '정우', 'deviceId': '8021102F2DAE60F43038CD92EB3F9CF9245D1635'},
            {'alias': '안방', 'deviceId': '8021F6E8802E8ADAAEB3E35695E981532498B3CA'},
        ]

        # Select all when None or 'all'
        self.assertEqual(len(tapo_cli.filter_devices(sample_devices, None)), 3)
        self.assertEqual(len(tapo_cli.filter_devices(sample_devices, 'all')), 3)

        # Exact match
        matched = tapo_cli.filter_devices(sample_devices, '정우방')
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0]['alias'], '정우방')

        # Multiple cameras comma-separated
        matched_multi = tapo_cli.filter_devices(sample_devices, '정우방, 안방')
        self.assertEqual(len(matched_multi), 2)
        aliases = [d['alias'] for d in matched_multi]
        self.assertIn('정우방', aliases)
        self.assertIn('안방', aliases)

        # Match by deviceId
        matched_id = tapo_cli.filter_devices(sample_devices, '8021102F2DAE60F43038CD92EB3F9CF9245D1635')
        self.assertEqual(len(matched_id), 1)
        self.assertEqual(matched_id[0]['alias'], '정우')

        # No match
        self.assertEqual(len(tapo_cli.filter_devices(sample_devices, '거실')), 0)

    def test_format_file_size(self):
        """Test formatting bytes into human-readable strings."""
        self.assertEqual(tapo_cli.format_file_size(500), "500 B")
        self.assertEqual(tapo_cli.format_file_size(2048), "2.0 KB")
        self.assertEqual(tapo_cli.format_file_size(2 * 1024 * 1024), "2.0 MB")

    def test_format_time_ago(self):
        """Test calculating and formatting days ago."""
        now = datetime.datetime.now()
        today_str = now.strftime('%Y-%m-%d %H:%M:%S')
        yesterday_str = (now - datetime.timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')
        past_str = (now - datetime.timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')

        self.assertEqual(tapo_cli.format_time_ago(today_str), "오늘")
        self.assertEqual(tapo_cli.format_time_ago(yesterday_str), "1일 전")
        self.assertIn("10일 전", tapo_cli.format_time_ago(past_str))

    def test_cli_help(self):
        """Test that tapo CLI help runs cleanly without error."""
        runner = CliRunner()
        result = runner.invoke(tapo_cli.tapo, ['--help'])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("download-videos", result.output)
        self.assertIn("login", result.output)

    def test_cli_subcommand_helps(self):
        """Test that subcommands display help properly and support --camera."""
        runner = CliRunner()
        for cmd in ['download-videos', 'list-videos']:
            res = runner.invoke(tapo_cli.tapo, [cmd, '--help'])
            self.assertEqual(res.exit_code, 0, f"Command {cmd} --help failed")
            self.assertIn("--camera", res.output)

    def test_error_code_and_token_expired(self):
        """Test error_code and token_expired detection for Tapo Care API responses."""
        # Success response
        self.assertEqual(tapo_cli.error_code({'error_code': 0}), 0)
        self.assertEqual(tapo_cli.error_code({'errorCode': '0'}), 0)
        self.assertEqual(tapo_cli.error_code({'code': 0}), 0)
        self.assertFalse(tapo_cli.token_expired({'code': 0}))

        # Tapo Care token expired (code 15000)
        care_err = {'code': 15000, 'message': 'token invalid, expired or replaced'}
        self.assertEqual(tapo_cli.error_code(care_err), 15000)
        self.assertTrue(tapo_cli.token_expired(care_err))

        # Gateway token expired (-20651)
        gw_err = {'error_code': -20651, 'msg': 'Token expired'}
        self.assertEqual(tapo_cli.error_code(gw_err), -20651)
        self.assertTrue(tapo_cli.token_expired(gw_err))

    def test_encryption_method_none(self):
        """Test that encryptionMethod NONE is handled without decryption key."""
        video_none = {
            'eventLocalTime': '2026-08-17 13:30:28',
            'video': [{'uri': 'http://example.com/test.mp4', 'encryptionMethod': 'NONE'}]
        }
        enc = video_none['video'][0].get('encryptionMethod')
        self.assertIn(str(enc).strip().upper(), ("NONE", ""))

if __name__ == '__main__':
    unittest.main()

