
import sys
import os
import asyncio
import unittest
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append("/home/pi/dataset_collector")

class TestSFTPTrigger(unittest.TestCase):
    def setUp(self):
        # Ensure paramiko is mocked in sys.modules BEFORE any import
        self.mock_paramiko = MagicMock()
        self.patcher = patch.dict(sys.modules, {'paramiko': self.mock_paramiko})
        self.patcher.start()
        
        # Now we can safely import sftp_handler
        if 'sftp_handler' in sys.modules:
            del sys.modules['sftp_handler']
        import sftp_handler
        self.sftp_handler_module = sftp_handler

    def tearDown(self):
        self.patcher.stop()

    def test_sftp_import(self):
        """Test that we can import the handler"""
        self.assertTrue(hasattr(self.sftp_handler_module, 'SFTPHandler'))

    def test_trigger_logic(self):
        """Simulate the logic in main.py without running the full app"""
        pending_transfers = []
        
        # Simulate capturing 10 files
        for i in range(10):
            pending_transfers.append(f"/tmp/file_{i}.jpg")
        
        triggered = False
        batch = []
        
        # Logic from main.py
        if len(pending_transfers) >= 10:
            triggered = True
            batch = list(pending_transfers)
            pending_transfers.clear()
            
        self.assertTrue(triggered)
        self.assertEqual(len(batch), 10)
        self.assertEqual(len(pending_transfers), 0)

    def test_handler_upload(self):
        """Test the handler upload logic with mocked paramiko"""
        
        # Setup mock
        mock_transport = MagicMock()
        mock_sftp = MagicMock()
        self.mock_paramiko.Transport.return_value = mock_transport
        self.mock_paramiko.SFTPClient.from_transport.return_value = mock_sftp
        
        # Create handler with dummy config
        with patch('builtins.open', new_callable=unittest.mock.mock_open, read_data='{"host": "test", "username": "user"}'):
             handler = self.sftp_handler_module.SFTPHandler()
        
        # Test upload
        with patch('os.path.exists', return_value=True):
            success = handler.upload_files(['/tmp/test.jpg'])
        
        self.assertTrue(success)
        mock_transport.connect.assert_called()
        mock_sftp.put.assert_called()

if __name__ == '__main__':
    unittest.main()
