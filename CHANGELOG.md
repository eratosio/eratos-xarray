# Changelog

### [v0.2.0] - 2025-07-04

- Fill values returned by the gridded data interface will now be passed into [`xarray.Variable`](https://docs.xarray.dev/en/stable/generated/xarray.Variable.html) via the `encoding` and `attrs` properties.
