from typing import List

import pytest

from tgftools.filehandler import RegionInformation


def test_region_information():
    """Check that the RegionInformation class works as expected. This is a fixed resource within the framework because
    it does not change between different analyses."""
    r = RegionInformation()

    # Check read-in of 'Côte d'Ivoire' is correct
    assert "Côte d'Ivoire" == r.region.loc['CIV'].GeographyName

    # Check that we can nterchange between country name and iso3 codes
    assert all([
        country_name == r.get_country_name_from_iso(r.get_iso_for_country(country_name))
        for country_name in ['Aruba', 'Afghanistan', 'Angola']
    ])

    # Get the list of ISO3 codes for a particular region
    c = r.get_countries_in_region("Central Africa")
    assert isinstance(c, List) and (len(c) > 0)

    # Get the region for a particular ISO3 code
    assert all([r.get_region_for_iso(country) == 'Central Africa' for country in c])
    assert 'High Impact Africa 2' == r.get_region_for_iso('ZWE')

    # Get list of ISO3 codes for a particular World Bank region
    wb_c = r.get_countries_in_wbregion("Sub-Saharan Africa")
    assert isinstance(wb_c, List) and (len(wb_c) > 0)

    # Get the World Bank region for particular ISO3 code
    assert all([r.get_wbregion_for_iso(country) == 'Sub-Saharan Africa' for country in wb_c])
    assert 'Sub-Saharan Africa' == r.get_wbregion_for_iso('ZWE')


def test_get_countries_by_regional_flag():
    """Check that the RegionInformation class works as expected when getting countries by regional flag."""

    r = RegionInformation()

    # Check performance with recognised flags
    for flag in ('ARABLEAGUE', 'COE', 'Johannes', 'OIC', 'PKU', 'SSA'):
        x = r.get_countries_by_regional_flag(flag)
        assert isinstance(x, List) and (len(x) > 0)

    # Check performance with unrecognised flag
    with pytest.raises(ValueError):
        r.get_countries_by_regional_flag('INVALID_FLAG')
