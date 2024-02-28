import xarray

import numpy as np
from packaging import version

from eratos.adapter import Adapter
from eratos.creds import AccessTokenCreds
from eratos.data import Data, GSData

import xarray
from xarray.backends import StoreBackendEntrypoint
from xarray.backends.common import BACKEND_ENTRYPOINTS
from xarray import Variable
from xarray.core import indexing
from xarray.core.utils import Frozen, FrozenDict, close_on_error
from xarray.core.pycompat import integer_types
from xarray.backends.common import AbstractDataStore, BackendArray, BackendEntrypoint


class EratosBackendArray(BackendArray):
    def __init__(
            self,
            gdata: GSData,
            var: str
    ):
        self.gdata = gdata
        self.var = var
        self.var_dimensions = gdata.spaces()[var]['dimensions']
        self.all_dimensions = gdata.dimensions()
        self.shape = ()
        for dim_name in self.var_dimensions:
            self.shape = self.shape + (self.all_dimensions[dim_name]['size'],)

        self.dtype = np.dtype(gdata.variables()[var]['dataType'])

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

        for n, k in enumerate(key):
            default_stop = self.all_dimensions[self.var_dimensions[n]]['size']

            if isinstance(k, slice):
                starts.append(k.start if k.start else 0)
                ends.append(k.stop if k.stop else default_stop)
                strides.append(k.step if k.step else 1)
            elif isinstance(k, integer_types):
                starts.append(k)
                ends.append(k+1)
                strides.append(1)

        array = self.gdata.get_subset_as_array(self.var, starts, ends, strides)

        # axis is a tuple, containing the index of each dimension selected by integer
        axis = tuple(n for n, k in enumerate(key) if isinstance(k, integer_types))

        # If the returned array hdoes not have the expected number of dimensions, then remove integer selected dimensions out.
        if (array.ndim != self.ndim - len(axis)) and axis:
            array = np.squeeze(array, axis)

        # TODO: how to properly handle missing values???
        # Currently Eratos SDK returns raw data arrays, and does not expose the missing vlaue metadata of underlying netcdf

        return array


class EratosBackendEntrypoint(BackendEntrypoint):
    description = "Open remote datasets via Eratos SDK"
    url = 'https://docs.eratos.com/docs'
    open_dataset_parameters = ['eratos_auth']

    def guess_can_open(
            self,
            filename_or_obj):
        return filename_or_obj.startswith('ern:')

    def open_dataset(
            self,
            filename_or_obj,
            *,
            decode_times=True,
            drop_variables=None,
            eratos_auth: AccessTokenCreds = None
    ):
        store = EratosDataStore.open(
            ern=filename_or_obj,
            eratos_auth=eratos_auth
        )

        store_entrypoint = StoreBackendEntrypoint()
        with close_on_error(store):
            ds = store_entrypoint.open_dataset(store, decode_times=decode_times)
            return ds


class EratosDataStore(AbstractDataStore):
    def __init__(self, gsdata):
        self.gsdata = gsdata

    @classmethod
    def open(cls, ern, eratos_auth: AccessTokenCreds = None):
        adapter = Adapter(eratos_auth)
        resource = adapter.Resource(ern=ern)
        data: Data = resource.data()
        gsdata: GSData = data.gapi()
        return cls(gsdata)

    def open_store_variable(self, var):
        backend_array = EratosBackendArray(gdata=self.gsdata, var=var)
        data = indexing.LazilyIndexedArray(backend_array)
        dimensions = list(backend_array.var_dimensions)

        # Leverage Xarray cf time decoder as all 'time' variable responses are treated as unix time.
        attrs = {'units': 'seconds since 1970-01-01 00:00:00'} if var == 'time' else {}

        return Variable(dimensions, data, attrs)

    def get_variables(self):
        return FrozenDict((k, self.open_store_variable(k)) for k in self.gsdata.variables().keys())

    def get_attrs(self):
        return Frozen({})

    def get_dimensions(self):
        return Frozen(self.gsdata.dimensions().keys())


if version.parse(xarray.__version__) >= version.parse('2023.4.0'):
    BACKEND_ENTRYPOINTS["eratos"] = ('eratos', EratosBackendEntrypoint)
else:
    # noinspection PyTypeChecker
    BACKEND_ENTRYPOINTS["eratos"] = EratosBackendEntrypoint
