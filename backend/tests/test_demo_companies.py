"""Новые демо-ID используют прежние маршруты и проверку company scope."""
import os
from pathlib import Path
import sys
from unittest import TestCase
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.api.main import app
from app.services import company_service
from app.settings import Settings

IDS=('U_44564','U_19717','U_9250')


class DemoCompaniesTests(TestCase):
    def test_default_demo_ids(self):
        self.assertEqual(Settings.model_fields['demo_company_ids'].default, ','.join(IDS))

    def test_three_companies_two_roles_and_company_scope(self):
        def row(cid):
            return [{'SYNTHETIC_U':cid,'CL_TYPE':'CLIENT'}] if cid in IDS else []
        with patch.dict(os.environ, {'DEMO_COMPANY_IDS':','.join(IDS),'ML_ADAPTER_MODULE':''}), patch.object(company_service,'get_company_raw',side_effect=row), TestClient(app) as client:
            profiles=client.get('/api/v1/demo-profiles')
            self.assertEqual(profiles.status_code,200)
            self.assertEqual({(x['company_id'],x['role']) for x in profiles.json()['items']}, {(cid,role) for cid in IDS for role in ('ceo','cfo')})
            for cid in IDS:
                self.assertEqual(client.get('/api/v1/companies/'+cid,headers={'X-Company-ID':cid}).status_code,200)
            denied=client.get('/api/v1/companies/'+IDS[1],headers={'X-Company-ID':IDS[0]})
            self.assertEqual(denied.status_code,403)
