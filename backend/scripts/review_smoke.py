"""HTTP acceptance check for compose.review.yml only; no external AI calls."""
import argparse
import json
import time
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://localhost:3100')
    args = parser.parse_args()
    base = args.base_url.rstrip('/')
    company = 'U_44564'

    def request(path, body=None, expected=200, selected=company, key=None):
        headers = {'X-Company-ID': selected, 'Content-Type': 'application/json'}
        if key:
            headers['Idempotency-Key'] = key
        req = Request(base + path, headers=headers,
                      data=json.dumps(body).encode() if body is not None else None)
        try:
            response = urlopen(req, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            payload = response.read().decode()
            if response.status != expected:
                raise RuntimeError(f'{path}: expected {expected}, got {response.status}: {payload}')
            return json.loads(payload)

    profiles = request('/api/v1/demo-profiles')['items']
    assert {(p['company_id'], p['role']) for p in profiles} == {
        (cid, role) for cid in ('U_44564', 'U_19717', 'U_9250') for role in ('ceo', 'cfo')}
    for profile in profiles:
        cid, role = profile['company_id'], profile['role']
        request('/api/v1/companies/' + cid, selected=cid)
        feed = request(f'/api/v1/feed?company_id={cid}&role={role}', selected=cid)
        assert any(item['id'] == 'review_news_1'
                   for item in feed['items'])
    request('/api/v1/companies/U_19717', expected=403)
    news = request('/api/v1/news/review_news_1')
    assert news['is_synthetic'] is True
    key = 'review-' + uuid.uuid4().hex
    body = {'company_id': company, 'role': 'cfo', 'news_id': 'review_news_1'}
    accepted = request('/api/v1/analyses', body, 202, key=key)
    assert request('/api/v1/analyses', body, 202, key=key)['analysis_id'] == accepted['analysis_id']
    path = '/api/v1/analyses/' + accepted['analysis_id']
    deadline = time.monotonic() + 90
    while True:
        analysis = request(path)
        if analysis['status'] == 'completed':
            break
        if analysis['status'] == 'failed' or time.monotonic() >= deadline:
            raise RuntimeError(f'Analysis did not complete: {analysis}')
        time.sleep(2)
    assert analysis['result']['sources']
    request(path + '/trace')
    reply = request('/api/v1/chat/messages',
                    {'analysis_id': accepted['analysis_id'], 'message': 'Что изменилось в учебном сценарии?'}, key=key)
    assert reply['status'] == 'completed' and reply['evidence_ids']
    assert len(request(path + '/messages')['items']) >= 2
    saved = request(f'/api/v1/my-analyses?company_id={company}&role=cfo')
    assert saved['total'] >= 1
    print('PASS: six profiles, feed, company scope, idempotency, queued -> completed, evidence, chat, saved analyses.')
    print('Synthetic adapter only: this does not measure real LLM quality or live RSS availability.')


if __name__ == '__main__':
    main()
