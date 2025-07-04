import pytest
from .conftest import KEY, NO_ERATOS_PLATFORM, SECRET, USE_ERATOS_PLATFORM_LOCALHOST
from dotenv import load_dotenv
import xarray as xr
import numpy as np

from pathlib import Path

from eratos.dsutil import netcdf
from eratos.data import Data
from eratos.dsutil.netcdf import _DEFAULT_FILL


@pytest.mark.parametrize(
    "dtype", ["f4", "f8", "u1", "u2", "u4", "u8", "i2", "i4", "i8"]
)
@pytest.mark.skipif(NO_ERATOS_PLATFORM, reason="No Eratos platform integration.")
def test_fillvalues(
    adapter, namespace, node_ern, dtype, tmp_path, get_sample_netcdf_missing_vals
):
    ds = get_sample_netcdf_missing_vals(
        np.datetime64("2025-01-01"), np.datetime64("2025-01-03"), data_type=dtype
    )
    fill = ds.variables["blah"].encoding["_FillValue"]
    print(f"Generated dataset fill: {fill}")
    print(f"Generated dataset dtype: {ds.variables['blah'].dtype}")
    print(f"Using default return fill value: {_DEFAULT_FILL[dtype]}")

    file_path = (tmp_path / "sample.nc").as_posix()
    ds.to_netcdf(file_path)
    fmap = {"sample.nc": file_path}
    connector_props = netcdf.gridded_geotime_netcdf_props({"sample.nc": file_path})
    ern = f"ern:e-pn.io:resource:{namespace}.tests.{dtype}-fillvalue-test"
    res = adapter.Resource(
        content={
            "@id": ern,
            "@type": "ern:e-pn.io:schema:dataset",
            "description": "Integration test - fill value",
            "type": "ern:e-pn.io:resource:eratos.dataset.type.gridded",
            "updateSchedule": "ern:e-pn.io:resource:eratos.schedule.noupdate",
            "name": "Integration test fill value",
        }
    )
    res.save()

    data = res.data()
    data.push_objects(node_ern, fmap, Data.GRIDDED_V1, connector_props)

    ds_returned = xr.open_dataset(ern, engine="eratos", eratos_adapter=adapter)
    # check fill value is equal
    assert ds_returned.variables["blah"].encoding["_FillValue"] == _DEFAULT_FILL[dtype]

    # check xarray mask method works properly
    ds_returned.load(mask_and_scale=True)
    mask = ds.variables["blah"].values == fill
    assert np.all(np.isnan(ds_returned["blah"].values[mask]))
