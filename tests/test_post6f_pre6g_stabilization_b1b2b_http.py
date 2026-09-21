"""B1B2B authenticated no-store transport on the app's existing test runtime."""
from hashlib import sha256
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from voxelatlas.volume_surfaces import VolumeSurfaceUnavailableError  # noqa: E402

class B1B2BRegionHttpTests(unittest.TestCase):
    def test_authenticated_endpoint_returns_only_bound_no_store_labels(self):
        from fastapi.testclient import TestClient
        from voxelatlas import config
        from voxelatlas.app import create_app
        from voxelatlas.passwords import hash_password

        class FakeService:
            def region_evidence_latest(self, *, surface_id):
                if surface_id != 'vsurf-' + '1' * 32:
                    raise VolumeSurfaceUnavailableError('No resident surface')
                labels = bytes([0, 1, 2, 1])
                return SimpleNamespace(
                    labels=labels, surface_id=surface_id, surface_sha256='a'*64,
                    labels_sha256=sha256(labels).hexdigest(), triangle_count=4,
                    face_counts=(1, 2, 1), body_region_count=2,
                    classification='not_anatomical',
                )

        with tempfile.TemporaryDirectory() as tmp:
            settings = config.AppSettings(
                environment='test', session_secret='x'*48, secure_cookies=False,
                session_cookie_name='voxelatlas_session',
                allowed_hosts=('testserver', '127.0.0.1', 'localhost'), data_dir=Path(tmp),
                max_upload_mib=512, auth_username='engineer',
                auth_password_hash=hash_password('synthetic test only'), session_ttl_minutes=60,
            )
            with TestClient(create_app(settings=settings, volume_surface_service=FakeService())) as client:
                url = '/api/studies/latest/volume-surface/regions?surface_id=' + 'vsurf-' + '1'*32
                self.assertEqual(client.get(url).status_code, 401)
                self.assertEqual(client.post('/api/auth/login', json={
                    'username':'engineer','password':'synthetic test only',
                }).status_code, 200)
                response = client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, bytes([0, 1, 2, 1]))
                self.assertEqual(response.headers['cache-control'], 'no-store')
                self.assertEqual(response.headers['x-content-type-options'], 'nosniff')
                self.assertEqual(response.headers['x-voxelatlas-volume-surface-id'], 'vsurf-' + '1'*32)
                self.assertEqual(response.headers['x-voxelatlas-volume-surface-sha256'], 'a'*64)
                self.assertEqual(response.headers['x-voxelatlas-region-face-counts'], '1,2,1')
                self.assertEqual(response.headers['x-voxelatlas-region-classification'], 'not_anatomical')
                self.assertEqual(client.get('/api/studies/latest/volume-surface/regions?surface_id=vsurf-stale').status_code, 409)


if __name__ == '__main__':
    unittest.main()
