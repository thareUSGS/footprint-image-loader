# LIFT - Load Image From Footprint

Select vector footprint features and load rasters referenced by the `filename` or `URL` attribute. Supports local base directories (with Browse) and HTTPS base URLs, groups imagery under a defined name, skips duplicate sources, reports failures, displays per-image progress, and allows cancelling between images. Images loaded before cancellation remain in the project.

Install the ZIP from QGIS Plugin Manager > Install from ZIP.

## Creating a GitHub release

Push a version tag to create a GitHub Release with an installable plugin ZIP:

```bash
git tag v0.4.0
git push origin v0.4.0
```

The release ZIP contains the plugin in a top-level `lift/` folder.

## License

LIFT - Load Image From Footprint is dedicated to the public domain under CC0 1.0 Universal. See [LICENSE](LICENSE).

Author: CoPilot A.I. (as defined by Trent Hare)
Date: October 2026
