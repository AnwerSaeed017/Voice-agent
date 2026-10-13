from datetime import date, datetime, timezone

import pytest

from app.tests.conftest import FixedClock
from app.utilities.field_normalizer import FieldNormalizer

TODAY = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def normalizer() -> FieldNormalizer:
    return FieldNormalizer(FixedClock(TODAY))


class TestCleanText:
    def test_collapses_whitespace_and_strips_control_characters(self, normalizer):
        assert normalizer.clean_text("  Spring\x00field \t\n City ") == "Spring field City"

    def test_empty_text_means_not_provided(self, normalizer):
        assert normalizer.clean_text("   ") is None

    def test_non_strings_pass_through(self, normalizer):
        assert normalizer.clean_text(42) == 42


class TestName:
    @pytest.mark.parametrize("value", ["Jane", "O'Connor-Reyes", "Mary Ann", "José", "J"])
    def test_accepts_real_names(self, normalizer, value):
        assert normalizer.name(value) == value

    def test_curly_apostrophe_becomes_straight(self, normalizer):
        assert normalizer.name("O’Neil") == "O'Neil"

    @pytest.mark.parametrize("value", ["J0rdan", "Verify@Home", "-", "Jordan'", "A" * 51])
    def test_rejects_invalid_names(self, normalizer, value):
        with pytest.raises(ValueError):
            normalizer.name(value)


class TestDateOfBirth:
    @pytest.mark.parametrize("value", ["03/05/1990", "1990-03-05", "03-05-1990"])
    def test_accepts_supported_formats(self, normalizer, value):
        assert normalizer.date_of_birth(value) == date(1990, 3, 5)

    def test_today_is_allowed(self, normalizer):
        assert normalizer.date_of_birth("01/15/2026") == date(2026, 1, 15)

    def test_leap_day(self, normalizer):
        assert normalizer.date_of_birth("02/29/2000") == date(2000, 2, 29)

    @pytest.mark.parametrize("value, reason", [
        ("01/16/2026", "future"),
        ("02/30/1990", "real calendar date"),
        ("02/29/1999", "real calendar date"),
        ("13/01/1990", "real calendar date"),
        ("yesterday", "real calendar date"),
        ("01/01/1850", "1900"),
    ])
    def test_rejects_invalid_dates(self, normalizer, value, reason):
        with pytest.raises(ValueError, match=reason):
            normalizer.date_of_birth(value)


class TestSex:
    @pytest.mark.parametrize("value, expected", [
        ("Male", "Male"), ("m", "Male"), ("FEMALE", "Female"), ("other", "Other"),
        ("prefer not to say", "Decline to Answer"), ("Decline to Answer", "Decline to Answer"),
    ])
    def test_maps_spoken_forms_to_the_stored_value(self, normalizer, value, expected):
        assert normalizer.sex(value) == expected

    def test_rejects_unknown_value(self, normalizer):
        with pytest.raises(ValueError, match="must be one of"):
            normalizer.sex("Robot")


class TestPhone:
    @pytest.mark.parametrize("value", ["4155550100", "(415) 555-0100", "+1 415 555 0100", "1-415-555-0100", 4155550100])
    def test_strips_formatting_and_country_code(self, normalizer, value):
        assert normalizer.phone(value) == "4155550100"

    @pytest.mark.parametrize("value", ["123", "24155550100", "call me", "415555010"])
    def test_rejects_anything_but_ten_digits(self, normalizer, value):
        with pytest.raises(ValueError, match="10-digit"):
            normalizer.phone(value)

    def test_error_says_how_many_digits_were_received(self, normalizer):
        with pytest.raises(ValueError, match="received 3 digits"):
            normalizer.phone("123")


class TestState:
    @pytest.mark.parametrize("value, expected", [("TX", "TX"), ("tx", "TX"), ("Texas", "TX"), ("district of columbia", "DC"), ("PR", "PR")])
    def test_accepts_abbreviation_or_full_name(self, normalizer, value, expected):
        assert normalizer.state(value) == expected

    def test_rejects_unknown_state(self, normalizer):
        with pytest.raises(ValueError):
            normalizer.state("ZZ")


class TestZipCode:
    @pytest.mark.parametrize("value, expected", [("62704", "62704"), ("62704-1234", "62704-1234"), ("627041234", "62704-1234"), (2108, "02108")])
    def test_accepts_five_digit_and_zip_plus_four(self, normalizer, value, expected):
        assert normalizer.zip_code(value) == expected

    @pytest.mark.parametrize("value", ["1234", "ABCDE", "62704-12"])
    def test_rejects_malformed_zip(self, normalizer, value):
        with pytest.raises(ValueError):
            normalizer.zip_code(value)


class TestEmailAndMemberId:
    def test_email_is_lowercased(self, normalizer):
        assert normalizer.email("MIXED.Case@Example.COM") == "mixed.case@example.com"

    @pytest.mark.parametrize("value", ["not-an-email", "a@b", "a b@example.com"])
    def test_rejects_malformed_email(self, normalizer, value):
        with pytest.raises(ValueError):
            normalizer.email(value)

    def test_member_id_is_compacted_and_uppercased(self, normalizer):
        assert normalizer.member_id("abc-123 456") == "ABC123456"

    def test_member_id_rejects_symbols(self, normalizer):
        with pytest.raises(ValueError):
            normalizer.member_id("AB#12")
