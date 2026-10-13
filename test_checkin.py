import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

import requests

from checkin import API, Checker, CheckinStatus, Config


RAILGUN_COOKIE = "koa:sess=railgun-example; koa:sess.sig=example"
GLADOS_COOKIE = "koa:sess=glados-example; koa:sess.sig=example; gld:sess=example; gld:sess.sig=example"


class FakeAdapter(requests.adapters.BaseAdapter):
    def __init__(self, respond):
        self.respond = respond
        self.requests = []

    def send(self, request, **kwargs):
        self.requests.append(request)
        response = requests.Response()
        response.status_code = 200
        response._content = json.dumps(self.respond(request)).encode()
        response.request = request
        return response

    def close(self):
        pass


class CheckinTests(unittest.TestCase):
    def setUp(self):
        self.logger = self.enterContext(patch("checkin.logger"))

    def run_checker(self, cookies, respond):
        adapter = FakeAdapter(respond)
        session_type = requests.Session

        def new_session():
            session = session_type()
            session.mount("https://", adapter)
            return session

        config = SimpleNamespace(
            cookies_list=cookies,
            DOMAINS=Config.DOMAINS,
            verbose=False,
            exchange_plan="plan500",
            EXCHANGE_PLANS=Config.EXCHANGE_PLANS,
        )
        checker = Checker(config)
        with patch("checkin.requests.Session", side_effect=new_session):
            checker.checkin_all()
        return checker, adapter.requests

    @staticmethod
    def site_response(request, points=25, checkin_code=0):
        url = urlsplit(request.url)
        expected_cookie = GLADOS_COOKIE if url.hostname == "glados.cloud" else RAILGUN_COOKIE
        if request.headers["cookie"] != expected_cookie:
            return {"code": -2, "message": "No permission"}
        if url.path == API.STATUS_URL:
            return {"code": 0, "data": {"leftDays": "23.5"}}
        if url.path == API.CHECKIN_URL:
            return {"code": checkin_code, "points": 1, "message": "Checkin response"}
        if url.path == API.POINTS_URL:
            return {"code": 0, "points": points}
        if url.path == API.EXCHANGE_URL:
            return {"code": 0}
        raise AssertionError(f"Unexpected path: {url.path}")

    def test_site_cookies_produce_two_checkins_without_cross_site_failures(self):
        checker, requests_sent = self.run_checker([RAILGUN_COOKIE, GLADOS_COOKIE], self.site_response)
        self.assertEqual([(r.cookie_index, r.domain, r.code) for r in checker.results], [
            (1, "railgun.info", CheckinStatus.SUCCESS),
            (2, "glados.cloud", CheckinStatus.SUCCESS),
        ])
        posts = [r for r in requests_sent if r.method == "POST"]
        self.assertEqual(len(posts), 2)
        for request in posts:
            self.assertEqual(request.headers["Content-Type"], "application/json")
            self.assertEqual(json.loads(request.body), {"token": urlsplit(request.url).hostname})
        self.assertEqual(posts[1].headers["cookie"], GLADOS_COOKIE)
        self.assertEqual([r.points for r in checker.results], ["1", "1"])
        title, _, summary = checker.format_results()
        self.assertIn("成功2, 失败0", title)
        self.assertIn("Cookie 1 @ railgun.info", summary)
        self.assertIn("Cookie 2 @ glados.cloud", summary)

    def test_cookie_rejected_by_both_sites_is_one_failure(self):
        expired_cookie = "koa:sess=expired-example"
        checker, requests_sent = self.run_checker([expired_cookie], self.site_response)
        self.assertEqual(len(checker.results), 1)
        self.assertEqual(checker.results[0].status, "Cookie 无效或已过期")
        self.assertTrue(all(r.method == "GET" for r in requests_sent))
        messages = str(self.logger.mock_calls)
        self.assertIn("gld:sess", messages)
        self.assertNotIn(expired_cookie, messages)

    def test_network_failure_does_not_become_cookie_rejection_or_send_posts(self):
        def network_failure(request):
            raise requests.ConnectionError("Unavailable")

        checker, requests_sent = self.run_checker([GLADOS_COOKIE], network_failure)
        self.assertTrue(all(r.method == "GET" for r in requests_sent))
        self.assertTrue(all(r.status == "状态查询失败，未执行签到" for r in checker.results))
        self.assertEqual(len(checker.results), 2)

    def test_missing_status_code_does_not_authorize_checkin(self):
        checker, requests_sent = self.run_checker([GLADOS_COOKIE], lambda request: {"data": {"leftDays": 10}})
        self.assertTrue(all(r.method == "GET" for r in requests_sent))
        self.assertTrue(all(r.code == CheckinStatus.FAILURE for r in checker.results))

    def test_exchange_uses_json_plan_only_when_points_are_sufficient(self):
        checker, requests_sent = self.run_checker(
            [GLADOS_COOKIE], lambda request: self.site_response(request, points=500)
        )
        exchanges = [r for r in requests_sent if urlsplit(r.url).path == API.EXCHANGE_URL]
        self.assertEqual(len(exchanges), 1)
        self.assertEqual(exchanges[0].headers["Content-Type"], "application/json")
        self.assertEqual(json.loads(exchanges[0].body), {"planType": "plan500"})
        self.assertEqual(checker.results[0].exchange, "兑换成功: plan500")

    def test_failed_checkin_stops_points_and_exchange_requests(self):
        checker, requests_sent = self.run_checker(
            [GLADOS_COOKIE], lambda request: self.site_response(request, points=500, checkin_code=-2)
        )
        self.assertEqual(checker.results[0].code, CheckinStatus.FAILURE)
        self.assertFalse(any(urlsplit(r.url).path in (API.POINTS_URL, API.EXCHANGE_URL) for r in requests_sent))
        self.assertIn("gld:sess", str(self.logger.mock_calls))

    def test_points_query_failure_is_not_reported_as_insufficient_balance(self):
        def points_failure(request):
            if urlsplit(request.url).path == API.POINTS_URL:
                return {"code": -2, "message": "No permission"}
            return self.site_response(request)

        checker, requests_sent = self.run_checker([GLADOS_COOKIE], points_failure)
        self.assertEqual(checker.results[0].exchange, "积分查询失败，未兑换")
        self.assertFalse(any(urlsplit(r.url).path == API.EXCHANGE_URL for r in requests_sent))

    def test_repeat_checkin_remains_a_repeat_result(self):
        checker, _ = self.run_checker(
            [GLADOS_COOKIE], lambda request: self.site_response(request, checkin_code=1)
        )
        self.assertEqual(checker.results[0].code, CheckinStatus.REPEAT)
        self.assertIn("重复1", checker.format_results()[0])


if __name__ == "__main__":
    unittest.main()
