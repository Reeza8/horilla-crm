## ⚠️ This repository has moved

The official image is now **[`horilla/horilla-crm`](https://hub.docker.com/r/horilla/horilla-crm)**.

This mirror still receives every stable release, so existing `docker pull horilla/crm` deployments keep working — nothing breaks today. But new tags, documentation and support all target `horilla/horilla-crm` first.

**To switch,** change the image name in your compose file or deployment:

```diff
- image: horilla/crm:latest
+ image: horilla/horilla-crm:latest
```

Both names are built from the same commit and are byte-identical. The examples below use the new name.
