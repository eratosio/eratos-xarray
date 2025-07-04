import os
from uuid import uuid4
import warnings
import string
import random

import pytest
import numpy as np
import xarray as xr

from eratos.creds import AccessTokenCreds
from eratos.adapter import Adapter
from eratos.errors import CommError
from eratos.dsutil.netcdf import _MAX_FLOAT64_PRECISION

from dotenv import load_dotenv

load_dotenv(override=True)

KEY = os.getenv("ERATOS_KEY")
SECRET = os.getenv("ERATOS_SECRET")

LOCAL_DEV_KEY = "7VRRBYBMQCHMJW2KMUE4Q4GY"
LOCAL_DEV_SECRET = "6kS98wDY9mMfaZwZ5wxzvRbO5PxPzoU5Eh59bruYvAE="
USE_ERATOS_PLATFORM_LOCALHOST = int(os.getenv("USE_ERATOS_PLATFORM_LOCALHOST", "0"))

NO_ERATOS_PLATFORM = (not KEY or not SECRET) and not USE_ERATOS_PLATFORM_LOCALHOST


@pytest.fixture
def get_sample_netcdf_missing_vals():
    def _method(start_date: np.datetime64, end_date: np.datetime64, data_type: str):
        lat_size = 5
        lon_size = 5
        dates = np.arange(
            start_date,
            end_date,
            dtype="datetime64[D]",
        )
        shape = (dates.shape[0], lat_size, lon_size)
        num_type = data_type[0]
        match data_type:
            case "u1" | "u2" | "u4" | "u8":
                info = np.iinfo(data_type)
                fill = np.random.randint(0, min(info.max, _MAX_FLOAT64_PRECISION))
                fill = np.array(fill, dtype=data_type).item()
                vals = np.random.randint(0, info.max, size=shape, dtype=data_type)
                vals = np.where(vals == fill, (fill + 1) % (info.max + 1), vals)

            case "i2" | "i4" | "i8":
                info = np.iinfo(data_type)
                fill = np.random.randint(
                    max(info.min, -1 * _MAX_FLOAT64_PRECISION),
                    min(info.max, _MAX_FLOAT64_PRECISION),
                )
                fill = np.array(fill, dtype=data_type).item()
                vals = np.random.randint(
                    max(info.min, -1 * _MAX_FLOAT64_PRECISION),
                    min(info.max, _MAX_FLOAT64_PRECISION),
                    size=shape,
                    dtype=data_type,
                )
                vals = np.where(vals == fill, fill + 1, vals)

            case "f4" | "f8":
                fill = np.random.uniform(-99, 99)
                fill = np.array(fill, dtype=data_type).item()
                vals = np.random.uniform(-99, 99, size=shape).astype(data_type)
                # optionally mask fill value
                vals = np.where(vals == fill, fill + 0.1, vals)

            case "c8" | "c16":
                fill = np.random.uniform(-99, 99) + np.random.uniform(0, 1) * 1j
                fill = np.array(fill, dtype=data_type).item()
                vals = (
                    np.random.uniform(-99, 99, size=shape)
                    + np.random.uniform(0, 1, size=shape) * 1j
                ).astype(data_type)
                # skip replacing fill — complex comparisons are tricky; may add a tolerance if needed

            case _:
                raise ValueError(f"Unsupported num_type: {num_type}")

        mask = np.random.choice(a=[0, 1], size=shape, p=[0.6, 0.4])

        ds = xr.Dataset(
            data_vars={
                "blah": (
                    ["time", "lat", "lon"],
                    np.where(mask, fill, vals),
                )
            },
            coords={
                "lat": ("lat", np.linspace(-34, -33, lat_size)),
                "lon": ("lon", np.linspace(143, 144, lon_size)),
                "time": ("time", dates),
            },
        )
        # cursed casting into type
        ds.variables["blah"].encoding["_FillValue"] = fill

        return ds

    return _method


@pytest.fixture(scope="session")
def adapter():
    if NO_ERATOS_PLATFORM:
        warnings.warn(
            "No Eratos platform integration - set ERATOS_KEY and ERATOS_SECRET environment variables"
        )
        return None
        # so other tests don't break
        raise ValueError(
            "No Eratos platform integration - set ERATOS_KEY and ERATOS_SECRET environment variables"
        )
    if USE_ERATOS_PLATFORM_LOCALHOST:
        print("Using localhost platform")
        ecreds = AccessTokenCreds(
            LOCAL_DEV_KEY, LOCAL_DEV_SECRET, "https://localhost:11080"
        )
        return Adapter(ecreds, ignore_certs=True)

    ecreds = AccessTokenCreds(KEY, SECRET, tracker="https://dev.e-tr.io")
    return Adapter(ecreds)


@pytest.fixture(scope="session", autouse=True)
def namespace(adapter):
    # random string for namespace here
    letters = string.ascii_lowercase
    namespace_id = "".join([random.choice(letters) for _ in range(8)])
    if adapter is None:
        yield None
    else:
        try:
            print("Creating namespace for integration test")
            ns = adapter.Resource(
                content={
                    "@type": "ern:e-pn.io:schema:namespace",
                    "key": namespace_id,
                    "name": f"Eratos Integration Test Namespace",
                    "description": f"Eratos Integration Test Namespace",
                }
            ).save()
            print(f"Created namespace: {namespace_id}")
            yield namespace_id
        except CommError as e:
            if e.code != 4006:
                raise
        finally:
            print("Removing temporary namespace for integration test.")
            ns.remove()


@pytest.fixture
def node_ern():
    if USE_ERATOS_PLATFORM_LOCALHOST:
        return "ern::node:test-cluster"
    else:
        return "ern::node:au-1.e-gn.io"
