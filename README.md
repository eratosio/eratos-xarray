# Xarray support for Eratos SDK

Provides an Xarray backend for Eratos SDK (<www.eratos.com>). The backend supports lazy loading remote datasets.

## Usage

Gridded datasets may be opened in `xarray` by passing in a valid ERN to the path argument and then supplying either an Eratos credentials object to `eratos_auth`
or an Eratos adapter object to `eratos_adapter`.

See below for a minimal example to open the SILO maximum temperature dataset.

```python

from eratos.creds import AccessTokenCreds
import xarray as xr

eratos_id = 'ENTER YOUR ERATOS ID'
eratos_secret = 'ENTER YOUR ERATOS SECRET KEY'

ecreds = AccessTokenCreds(eratos_id, eratos_secret)
silo = xr.open_dataset('ern:e-pn.io:resource:eratos.blocks.silo.maxtemperature', eratos_auth=ecreds)

print(silo)
```

alternatively an initialised adapter object can be passed through. This is useful to reuse the same session.

```python

from eratos.creds import AccessTokenCreds
from eratos.adapter import Adapter
import xarray as xr

eratos_id = 'ENTER YOUR ERATOS ID'
eratos_secret = 'ENTER YOUR ERATOS SECRET KEY'

ecreds = AccessTokenCreds(eratos_id, eratos_secret)
adapter = Adapter(ecreds)
silo = xr.open_dataset('ern:e-pn.io:resource:eratos.blocks.silo.maxtemperature', eratos_adpater=adapter)

print(silo)
```
