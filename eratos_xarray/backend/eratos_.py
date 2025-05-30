import xarray

import numpy as np
from packaging import version

from eratos.adapter import Adapter
from eratos.creds import BaseCreds
from eratos.data import Data, GSData

from xarray.backends import StoreBackendEntrypoint
from xarray.backends.common import BACKEND_ENTRYPOINTS
from xarray import Variable
from xarray.core import indexing
from xarray.core.utils import Frozen, FrozenDict, close_on_error
from xarray.core.pycompat import integer_types
from xarray.backends.common import AbstractDataStore, BackendArray, BackendEntrypoint

from typing import Optional


class EratosBackendArray(BackendArray):
    def __init__(self, gdata: GSData, var: str):
        self.gdata = gdata
        self.var = var
        self.var_dimensions = gdata.spaces()[var]["dimensions"]
        self.all_dimensions = gdata.dimensions()
        self.shape = ()
        for dim_name in self.var_dimensions:
            self.shape = self.shape + (self.all_dimensions[dim_name]["size"],)

        self.dtype = np.dtype(gdata.variables()[var]["dataType"])

    def __getitem__(self, key: indexing.ExplicitIndexer) -> np.typing.ArrayLike:
        return indexing.explicit_indexing_adapter(
            key,
            self.shape,
            indexing.IndexingSupport.BASIC,
            self._raw_indexing_method,
        )

    def _raw_indexing_method(self, key: tuple) -> np.typing.ArrayLike:
        starts = []
        ends = []
        strides = []
        any_empty = False
        new_shape = list(self.shape)
        for n, k in enumerate(key):
            default_stop = self.all_dimensions[self.var_dimensions[n]]["size"]

            if isinstance(k, slice):
                # check for slicing beyond start and end
                starts.append(k.start if k.start else 0)
                ends.append(k.stop if k.stop else default_stop)
                strides.append(k.step if k.step else 1)
                if (k.start == default_stop) or (k.stop == 0):
                    any_empty = True
                    new_shape[n] = 0
                else:
                    new_shape[n] = ends[n] - starts[n]
            elif isinstance(k, integer_types):
                starts.append(k)
                ends.append(k + 1)
                strides.append(1)
        if any_empty:
            return np.empty(shape=tuple(new_shape))

        array = self.gdata.get_subset_as_array(self.var, starts, ends, strides)

        # axis is a tuple, containing the index of each dimension selected by integer
        axis = tuple(n for n, k in enumerate(key) if isinstance(k, integer_types))

        # If the returned array hdoes not have the expected number of dimensions, then remove integer selected dimensions out.
        if (array.ndim != self.ndim - len(axis)) and axis:
            array = np.squeeze(array, axis)
        return array


class EratosBackendEntrypoint(BackendEntrypoint):
    description = "Open remote datasets via Eratos SDK"
    url = "https://docs.eratos.com/docs"
    open_dataset_parameters = ["eratos_auth"]

    def guess_can_open(self, filename_or_obj):
        return filename_or_obj.startswith("ern:")

    def open_dataset(
        self,
        filename_or_obj,
        *,
        decode_times=True,
        drop_variables=None,
        eratos_auth: Optional[BaseCreds] = None,
        ignore_certs: bool = False,
        eratos_adapter: Optional[Adapter] = None,
    ):
        store = EratosDataStore.open(
            ern=filename_or_obj,
            eratos_auth=eratos_auth,
            ignore_certs=ignore_certs,
            eratos_adapter=eratos_adapter,
        )

        store_entrypoint = StoreBackendEntrypoint()
        with close_on_error(store):
            ds = store_entrypoint.open_dataset(store, decode_times=decode_times)
            return ds


class EratosDataStore(AbstractDataStore):
    def __init__(self, gsdata):
        self.gsdata = gsdata

    @classmethod
    def open(
        cls,
        ern,
        eratos_auth: Optional[BaseCreds] = None,
        ignore_certs: bool = False,
        eratos_adapter: Optional[Adapter] = None,
    ):
        if eratos_adapter:
            adapter = eratos_adapter
        elif eratos_auth:
            adapter = Adapter(eratos_auth, ignore_certs=ignore_certs)
        else:
            raise ValueError("Need Eratos creds or adapter object")
        resource = adapter.Resource(ern=ern)
        data: Data = resource.data()
        gsdata: GSData = data.gapi()
        return cls(gsdata)

    def open_store_variable(self, var):
        backend_array = EratosBackendArray(gdata=self.gsdata, var=var)
        data = indexing.LazilyIndexedArray(backend_array)
        dimensions = list(backend_array.var_dimensions)

        # Leverage Xarray cf time decoder as all 'time' variable responses are treated as unix time.
        attrs = {"units": "seconds since 1970-01-01 00:00:00"} if var == "time" else {}
        fill_val = self.gsdata.variables()[var].get("fillValue", None)
        encoding = None
        if fill_val:
            # attrs["_FillValue"] = fill_val
            encoding = {"_FillValue": fill_val}

        return Variable(dimensions, data, attrs, encoding=encoding)

    def get_variables(self):
        return FrozenDict(
            (k, self.open_store_variable(k)) for k in self.gsdata.variables().keys()
        )

    def get_attrs(self):
        return Frozen({})

    def get_dimensions(self):
        return Frozen(self.gsdata.dimensions().keys())


if version.parse(xarray.__version__) >= version.parse("2023.4.0"):
    BACKEND_ENTRYPOINTS["eratos"] = ("eratos", EratosBackendEntrypoint)
else:
    # noinspection PyTypeChecker
    BACKEND_ENTRYPOINTS["eratos"] = EratosBackendEntrypoint
