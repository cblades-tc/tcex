"""TcEx Framework Module"""

# standard library
import os
from random import randint

# third-party
from _pytest.fixtures import FixtureRequest

# first-party
from tcex.tcex import TcEx
from tests.api.tc.v2.threat_intelligence.ti_helper import TestThreatIntelligence, TIHelper


class TestHashTagIndicators(TestThreatIntelligence):
    """Test TcEx Hash Tag Indicators."""

    indicator_field = 'Hashtag'
    indicator_field_arg = indicator_field.replace(' ', '_').lower()
    indicator_type = 'Hashtag'
    owner = os.getenv('TC_OWNER')
    tcex: TcEx

    def setup_method(self):
        """Configure setup before all tests."""
        self.ti_helper = TIHelper(self.indicator_type, self.indicator_field_arg)
        self.ti = self.ti_helper.ti
        self.tcex = self.ti_helper.tcex


    def tests_ti_hashtag_create(self):
        """Create an indicator using specific interface."""
        indicator_data = {
            self.indicator_field_arg: self.ti_helper.rand_hashtag(),
            'confidence': randint(0, 100),
            'owner': self.owner,
            'rating': randint(0, 5),
        }
        # hashtag method is dynamically generated
        ti = self.ti.hashtag(**indicator_data)  # type: ignore
        r = ti.create()

        # assert response
        assert r.status_code == 201

        # retrieve indicator for asserts (hashtag method is dynamically generated)
        ti = self.ti.hashtag(**indicator_data)  # type: ignore
        r = ti.single()
        response_data = r.json()
        ti_data = response_data.get('data', {}).get(ti.api_entity)

        # validate response data
        assert r.status_code == 200
        assert response_data.get('status') == 'Success'

        # validate ti data
        assert ti_data.get('confidence') == indicator_data.get('confidence')
        assert ti_data.get(self.indicator_field) == indicator_data.get(self.indicator_field_arg)
        assert ti_data.get('rating') == indicator_data.get('rating')

        # cleanup indicator
        r = ti.delete()
        assert r.status_code == 200

    def tests_ti_hashtag_add_attribute(self, request: FixtureRequest):
        """Test indicator add attribute."""
        super().indicator_add_attribute(request)

    def tests_ti_hashtag_add_label(self):
        """Test indicator add label."""
        super().indicator_add_label()

    def tests_ti_hashtag_add_tag(self, request: FixtureRequest):
        """Test indicator delete."""
        super().indicator_add_tag(request)

    def tests_ti_hashtag_delete(self):
        """Test indicator add tag."""
        super().indicator_delete()

    def tests_ti_hashtag_get(self):
        """Test indicator get with generic indicator method."""
        super().indicator_get()

    def tests_ti_hashtag_get_includes(self, request: FixtureRequest):
        """Test indicator get with includes."""
        super().indicator_get_includes(request)

    def tests_ti_hashtag_get_attribute(self, request: FixtureRequest):
        """Test indicator get attribute."""
        super().indicator_get_attribute(request)

    def tests_ti_hashtag_get_label(self):
        """Test indicator get label."""
        super().indicator_get_label()

    def tests_ti_hashtag_get_tag(self, request: FixtureRequest):
        """Test indicator get tag."""
        super().indicator_get_tag(request)

    def tests_ti_hashtag_update(self):
        """Test updating indicator metadata."""
        super().indicator_update()
