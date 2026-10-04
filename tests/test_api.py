import os
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from hq_service import client
from hq_service.app import app

TOKEN = 'test-only-not-a-real-token-' + 'x' * 40
VID = 'test_video_00001'


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {'HQ_API_TOKEN': TOKEN, 'HQ_RATE_LIMIT_PER_MINUTE': '60'})
        self.env.start()
        self.identity = patch('hq_service.client._guest_identity', return_value={})
        self.signer = patch('hq_service.signer._ensure_server', return_value='http://127.0.0.1:1234/sign')
        self.identity.start()
        self.signer.start()
        self.context = TestClient(app)
        self.http = self.context.__enter__()
        self.headers = {'Authorization': 'Bearer ' + TOKEN}

    def tearDown(self):
        self.context.__exit__(None, None, None)
        self.identity.stop()
        self.signer.stop()
        self.env.stop()

    def test_health_public_but_data_private(self):
        self.assertEqual(self.http.get('/healthz').status_code, 200)
        self.assertEqual(self.http.get('/v1/series/7686533063710346265').status_code, 401)
        self.assertEqual(self.http.get('/sign', headers=self.headers).status_code, 404)

    def test_series_fixed_action(self):
        with patch('hq_service.client.fetch_episode_list', return_value={'episode_count': 99}) as fn:
            response = self.http.get('/v1/series/7686533063710346265', headers=self.headers)
        self.assertEqual(response.json()['episode_count'], 99)
        self.assertEqual(response.headers['cache-control'], 'no-store')
        fn.assert_called_once_with('7686533063710346265')

    def test_invalid_id_no_upstream(self):
        with patch('hq_service.client.fetch_episode_list') as fn:
            self.assertEqual(self.http.get('/v1/series/not-an-id', headers=self.headers).status_code, 422)
            fn.assert_not_called()

    def test_invalid_models_body(self):
        for body in ({'vids': []}, {'vids': ['x']}, {'vids': [VID] * 51},
                     {'vids': [VID], 'url': 'http://localhost/secret'}):
            self.assertEqual(self.http.post('/v1/models', headers=self.headers, json=body).status_code, 422)

    def test_models_refresh(self):
        with patch('hq_service.client.invalidate_play_url') as invalidate, \
             patch('hq_service.client.prefetch_play_urls') as prefetch:
            response = self.http.post('/v1/models', headers=self.headers,
                                      json={'vids': [VID, VID], 'refresh': True})
        self.assertEqual(response.status_code, 200)
        invalidate.assert_called_once_with(VID)
        prefetch.assert_called_once_with([VID])

    def test_upstream_denied_and_error_redacted(self):
        for error, expected in [(client.AccessDeniedError('secret'), 403), (RuntimeError('secret-url'), 502)]:
            with patch('hq_service.client.fetch_episode_list', side_effect=error):
                response = self.http.get('/v1/series/7686533063710346265', headers=self.headers)
            self.assertEqual(response.status_code, expected)
            self.assertNotIn('secret', response.text)

    def test_rate_limit(self):
        app.state.rate = 1
        self.http.get('/v1/series/invalid', headers=self.headers)
        response = self.http.get('/v1/series/invalid', headers=self.headers)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers['retry-after'], '60')

    def test_no_docs_and_no_redirect_proxy(self):
        self.assertEqual(self.http.get('/docs', headers=self.headers).status_code, 404)
        self.assertEqual(self.http.post('/sign', json={}, headers=self.headers).status_code, 404)

    def test_refuse_oversized_body(self):
        response = self.http.post('/v1/models', content='x' * 65537, headers=self.headers)
        self.assertEqual(response.status_code, 413)


if __name__ == '__main__':
    unittest.main()
