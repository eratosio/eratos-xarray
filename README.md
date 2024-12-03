# Xarray support for Eratos SDK

Provides an Xarray backend for Eratos SDK (<www.eratos.com>). The backend supports lazy loading remote datasets.

### Getting Started

See below for a minimal example to open the SILO maximum temperature dataset.

```python

from eratos.creds import AccessTokenCreds
import xarray as xr

eratos_id = 'ENTER YOUR ERATOS ID'
eratos_secret = 'ENTER YOUR ERATOS SECRET KEY'

ecreds = AccessTokenCreds(eratos_id, eratos_secret)

silo = xr.open_dataset('ern:e-pn.io:resource:eratos.blocks.silo.maxtemperature',engine = 'eratos', eratos_auth=ecreds)

print(silo)
```

