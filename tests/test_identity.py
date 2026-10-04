import os
import unittest
from unittest.mock import patch
from hq_service import client


class IdentityTests(unittest.TestCase):
    def tearDown(self):
        client._identity = None

    def test_env_identity_stable_without_disk(self):
        identity = {'HQ_DEVICE_ID': '1000000000000001', 'HQ_IID': '1000000000000002',
                    'HQ_CDID': '11111111-1111-4111-8111-111111111111'}
        client._identity = None
        with patch.dict(os.environ, identity), patch('pathlib.Path.open') as disk:
            first = client._guest_identity()
            self.assertEqual(client._guest_identity(), first)
            self.assertEqual(first['device_id'], identity['HQ_DEVICE_ID'])
            disk.assert_not_called()

    def test_partial_profile_rejected(self):
        client._identity = None
        with patch.dict(os.environ, {'HQ_DEVICE_ID': '1000000000000001', 'HQ_IID': '', 'HQ_CDID': ''}):
            with self.assertRaises(RuntimeError):
                client._guest_identity()


if __name__ == '__main__':
    unittest.main()
