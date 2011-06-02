import os
import cStringIO
import unittest
import urllib2
import httplib

EXPECTED_REQUESTS = []

class RequestWrongOrder(Exception):
    """raised if an unexpected request is issued to urllib2"""
    def __init__(self, url, exp_url, method, exp_method):
        Exception.__init__(self)
        self.url = url
        self.exp_url = exp_url
        self.method = method
        self.exp_method = exp_method

    def __str__(self):
        return '%s, %s, %s, %s' % (self.url, self.exp_url,
                                   self.method, self.exp_method)

class RequestDataMismatch(Exception):
    """raised if POSTed or PUTed data doesn't match with the expected data"""
    def __init__(self, url, got, exp):
        self.url = url
        self.got = got
        self.exp = exp

    def __str__(self):
        return '%s, %s, %s' % (self.url, self.got, self.exp)

class MyHTTPHandler(urllib2.HTTPHandler):
    def __init__(self, *args, **kwargs):
        self._exp_requests = kwargs.pop('exp_requests')
        self._fixtures_dir = kwargs.pop('fixtures_dir')
        urllib2.HTTPHandler.__init__(self, *args, **kwargs)

    def http_open(self, req):
        r = self._exp_requests.pop(0)
        if req.get_full_url() != r[1] or req.get_method() != r[0]:
            raise RequestWrongOrder(req.get_full_url(), r[1], req.get_method(),
                                    r[0])
        if req.get_method() in ('GET', 'DELETE'):
            return self._mock_GET(r[1], **r[2])
        elif req.get_method() in ('PUT', 'POST'):
            return self._mock_PUT(req, **r[2])

    def _mock_GET(self, fullurl, **kwargs):
        return self._get_response(fullurl, **kwargs)

    def _mock_PUT(self, req, **kwargs):
        exp = kwargs.get('exp', None)
        if exp is not None and kwargs.has_key('expfile'):
            raise ValueError('either specify exp or expfile')
        elif kwargs.has_key('expfile'):
            filename = os.path.join(self._fixtures_dir, kwargs['expfile'])
            exp = open(filename, 'r').read()
        elif exp is None:
            raise ValueError('exp or expfile required')

        exp_content_type = kwargs.pop('exp_content_type', '')
        if exp_content_type:
            assert req.get_header('Content-type', '') == exp_content_type
        data = str(req.get_data())
        if exp is not None and data != exp:
            raise RequestDataMismatch(req.get_full_url(), repr(req.get_data()),
                                      repr(exp))
        return self._get_response(req.get_full_url(), **kwargs)

    def _get_response(self, url, **kwargs):
        f = None
        if kwargs.has_key('exception'):
            raise kwargs['exception']
        if not kwargs.has_key('text') and kwargs.has_key('file'):
            filename = os.path.join(self._fixtures_dir, kwargs['file'])
            f = cStringIO.StringIO(open(filename, 'r').read())
        elif kwargs.has_key('text') and not kwargs.has_key('file'):
            f = cStringIO.StringIO(kwargs['text'])
        else:
            raise ValueError('either specify text or file')
        resp = urllib2.addinfourl(f, {}, url)
        resp.code = kwargs.get('code', 200)
        resp.msg = ''
        return resp

def urldecorator(method, fullurl, **kwargs):
    def decorate(test_method):
        def wrapped_test_method(*args):
            add_expected_request(method, fullurl, **kwargs)
            test_method(*args)
        # "rename" method otherwise we cannot specify a TestCaseClass.testName
        # cmdline arg when using unittest.main()
        wrapped_test_method.__name__ = test_method.__name__
        return wrapped_test_method
    return decorate

def GET(fullurl, **kwargs):
    return urldecorator('GET', fullurl, **kwargs)

def PUT(fullurl, **kwargs):
    return urldecorator('PUT', fullurl, **kwargs)

def POST(fullurl, **kwargs):
    return urldecorator('POST', fullurl, **kwargs)

def DELETE(fullurl, **kwargs):
    return urldecorator('DELETE', fullurl, **kwargs)

def add_expected_request(method, url, **kwargs):
    global EXPECTED_REQUESTS
    EXPECTED_REQUESTS.append((method, url, kwargs))

class MockUrllib2Request(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        self._fixtures_dir = kwargs.pop('fixtures_dir', os.curdir)
        unittest.TestCase.__init__(self, *args, **kwargs)

    def fixture_file(self, filename):
        return os.path.join(self._fixtures_dir, filename)

    def setUp(self):
        global EXPECTED_REQUESTS
        EXPECTED_REQUESTS = []
        old_build_opener = urllib2.build_opener
        def build_opener(*handlers):
            handlers += (MyHTTPHandler(exp_requests=EXPECTED_REQUESTS,
                                       fixtures_dir=self._fixtures_dir), )
            return old_build_opener(*handlers)
        urllib2.build_opener = build_opener

    def tearDown(self):
        self.assertTrue(len(EXPECTED_REQUESTS) == 0)
