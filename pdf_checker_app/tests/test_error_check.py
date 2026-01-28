import logging

from django.conf import settings as project_settings

# from django.test import TestCase                  # TestCase requires db
from django.test import SimpleTestCase as TestCase  # SimpleTestCase does not require db
from django.test.utils import override_settings


log = logging.getLogger(__name__)
TestCase.maxDiff = 1000


class ErrorCheckTest(TestCase):
    """
    Checks urls.
    """

    @override_settings(DEBUG=True)  # for tests, DEBUG autosets to False
    def test_dev_errorcheck(self):
        """
        Checks that dev error_check url triggers error.
        """
        log.debug(f'debug, ``{project_settings.DEBUG}``')
        try:
            log.debug('about to initiate client.get()')
            self.client.get('/error_check/')
        except Exception as e:
            log.debug(f'e, ``{repr(e)}``')
            self.assertEqual(
                "Exception('Raising intentional exception to check email-admins-on-error functionality.')",
                repr(e),
            )

    def test_prod_errorcheck(self):
        """
        Checks that production error_check url returns 404.
        """
        log.debug(f'debug, ``{project_settings.DEBUG}``')
        response = self.client.get('/error_check/')
        self.assertEqual(404, response.status_code)
